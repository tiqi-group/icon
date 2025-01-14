from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple, TypedDict, cast

import yaml
from influxdb_client.client.flux_table import FluxRecord

from icon.config.config import get_config
from icon.config.v1 import InfluxDBConfig

try:
    from typing import Self
except ImportError:
    from typing_extensions import Self


from influxdb_client import (
    Bucket,  # type: ignore
    BucketRetentionRules,  # type: ignore
    BucketsApi,  # type: ignore
    InfluxDBClient,  # type: ignore
    Point,  # type: ignore
    WriteApi,  # type: ignore
    WritePrecision,  # type: ignore
)
from influxdb_client.client.write.point import DEFAULT_WRITE_PRECISION  # type: ignore
from influxdb_client.client.write_api import SYNCHRONOUS  # type: ignore
from influxdb_client.rest import ApiException  # type: ignore
from pydantic import SecretStr  # noqa (needs to be outside of TYPE_CHECKING block)

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime
    from types import TracebackType

    from reactivex import Observable

logger = logging.getLogger(__name__)
BUCKET_ALREADY_EXISTS = 422


class Record(TypedDict):
    value: Any
    measurement: str
    field: str
    tags: dict[str, str]
    time: datetime


class InfluxDBSession:
    """
    The `InfluxDBConnection` class serves as a context manager for a connection to an
    InfluxDB server. This connection is established using credentials provided through
    environment variables.

    Args:
        config_source: confz.ConfigSource
            Configuration source compatible with `icon.databases.config.InfluxDBConfig`,
            e.g. a `confz.DataSource`:

                ```python
                InfluxDBSession(
                    config_source=DataSource(
                        data={
                            "url": "<influxdb_url>",
                            "org": "<org>",
                            "token": "my-super-secret-auth-token",
                        }
                    )
                )
                ```

            or a `confz.FileSource`:

                ```python
                InfluxDBSession(
                    config_source=FileSource(file="/path/to/config/file.yaml")
                )
                ```

    Example:

        ```python
        with InfluxDBSession() as influx_client:
            # Creating a bucket
            influx_client.create_bucket(
                bucket_name='my_new_bucket', description='This is a new bucket'
            )

            # Writing data to a bucket
            record = {
                "measurement": "your_measurement",  # Replace with your measurement
                "tags": {
                    "example_tag": "tag_value",  # Replace with your tag and its value
                },
                "fields": {
                    "example_field": 123,  # Replace with your field and its value
                },
                "time": "2023-06-05T00:00:00Z",  # Replace with your timestamp
            }
            influx_client.write(
                bucket='my_new_bucket', record=record
            )
        ```
    """

    def __init__(self, config_source: Path | None = None) -> None:
        if config_source is None:
            self._config = get_config().databases.influxdb
        else:
            with config_source.open() as file:
                config = yaml.safe_load(file)
            self._config = InfluxDBConfig(**config)

        self.url = self._config.url
        self.token = self._config.token
        self.org = self._config.org
        self._client: InfluxDBClient
        self._write_api: WriteApi
        self._buckets_api: BucketsApi

    def __enter__(self) -> Self:
        self._client = InfluxDBClient(url=self.url, token=self.token, org=self.org)
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._query_api = self._client.query_api()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self._write_api.close()
        self._client.__del__()

    def write(
        self,
        bucket: str,
        record: str
        | Iterable[str]
        | Point
        | Iterable[Point]
        | dict[str, Any]
        | Iterable[dict[str, Any]]
        | bytes
        | Iterable[bytes]
        | Observable[Any]
        | NamedTuple
        | Iterable[NamedTuple],
        org: str | None = None,
        write_precision: WritePrecision = DEFAULT_WRITE_PRECISION,  # type: ignore
        **kwargs: Any,
    ) -> Any:
        self._write_api.write(  # type: ignore
            bucket=bucket,
            org=org if org is not None else self.org,
            record=record,
            write_precision=write_precision,  # type: ignore
            **kwargs,
        )

    def query_last(  # noqa: PLR0913
        self,
        bucket: str,
        org: str | None = None,
        measurement: str | None = None,
        fields: set[str] | None = None,
        tags: dict[str, str] | None = None,
        range_start: str = "0",
    ) -> list[Record]:
        query = f'from(bucket:"{bucket}") |> range(start: {range_start}) '
        if measurement:
            query += f'|> filter(fn: (r) => r["_measurement"] == "{measurement}")'

        if fields:
            field_conditions = [f'r["_field"] == "{field}"' for field in fields]
            field_filter = f"|> filter(fn: (r) => {' or '.join(field_conditions)})"
            query += field_filter

        if tags:
            tag_filters = " ".join(
                f'|> filter(fn: (r) => r["{key}"] == "{value}")'
                for key, value in tags.items()
            )
            query += tag_filters

        query += " |> last()"

        tables = self._query_api.query(
            query=query,
            org=org if org is not None else self.org,
        )
        return [
            Record(
                measurement=str(record.get_measurement()),  # type: ignore
                value=record.get_value(),  # type: ignore
                field=record.get_field(),  # type: ignore
                tags={
                    k: v
                    for k, v in record.values.items()
                    if not k.startswith("_") and k not in ("table", "result")
                },
                time=record.get_time(),  # type: ignore
            )
            for table in tables
            for record in cast(list[FluxRecord], table.records)
        ]

    def create_bucket(  # noqa: PLR0913
        self,
        bucket: Bucket | None = None,
        bucket_name: str | None = None,
        org_id: int | None = None,
        retention_rules: BucketRetentionRules | None = None,
        description: str | None = None,
        org: str | None = None,
    ) -> None:
        """
        Create a bucket in the InfluxDB instance. This function wraps the create_bucket
        from `influxdb_client` in a try-catch block and logs potential errors.

        Args:
            bucket (Bucket | PostBucketRequest, optional): Bucket instance to be
            created.
            bucket_name (str, optional): Name of the bucket to be created.
            org_id (int, optional): The organization id for the bucket.
            retention_rules (BucketRetentionRules, optional): Retention rules for the
            bucket.
            description (str, optional): Description of the bucket.
            org (str, optional): The name of the organization for the bucket. Takes
            the ID, Name, or Organization. If not specified, the default value from
            `InfluxDBClient.org` is used.
        """

        self._buckets_api = self._client.buckets_api()
        try:
            self._buckets_api.create_bucket(
                bucket=bucket,
                bucket_name=bucket_name,
                org_id=org_id,
                retention_rules=retention_rules,
                description=description,
                org=org,
            )
        except ApiException as e:
            if e.status == BUCKET_ALREADY_EXISTS:
                logger.debug(e.message)
                return
            logger.exception(e)
        return
