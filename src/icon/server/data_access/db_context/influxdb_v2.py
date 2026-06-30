from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, Literal

import influxdb_client
from influxdb_client.client.write_api import SYNCHRONOUS

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import (
    DatabaseValueType,
    escape_quotes,
)

if TYPE_CHECKING:
    from types import TracebackType

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

logger = logging.getLogger(__name__)


def is_responsive() -> bool:
    try:
        config = get_config().databases.influxdbv2
        with influxdb_client.InfluxDBClient(
            url=config.url,
            token=config.token,
            org=config.org,
            verify_ssl=config.verify_ssl,
        ) as client:
            health = client.health()
            return health.status == "pass"
    except Exception:
        return False


class InfluxDBv2Session:
    """Context manager for a synchronous connection to an InfluxDB v2 server.

    Credentials are loaded from the ICON configuration file.  The public
    interface mirrors `InfluxDBv1Session` so callers can be backend-agnostic.
    """

    def __init__(self) -> None:
        self._config = get_config().databases.influxdbv2
        self.bucket = self._config.bucket
        self.org = self._config.org
        self._client: Any
        self._write_api: Any
        self._query_api: Any

    def __enter__(self) -> Self:
        self.connect()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        exc_traceback: TracebackType | None,
    ) -> None:
        self.disconnect()

    def connect(self) -> None:
        """Open a connection and initialise write/query APIs."""
        self._client = influxdb_client.InfluxDBClient(
            url=self._config.url,
            token=self._config.token,
            org=self.org,
            verify_ssl=self._config.verify_ssl,
        )
        self._write_api = self._client.write_api(write_options=SYNCHRONOUS)
        self._query_api = self._client.query_api()

    def disconnect(self) -> None:
        """Close the active connection."""
        self._client.close()

    def write_points(
        self,
        points: list[dict[str, Any]],
        time_precision: Literal["s", "m", "ms", "u"] | None = None,
        _database: str | None = None,
        tags: dict[str, str] | None = None,
        _batch_size: int | None = None,
        _consistency: Literal["any", "one", "quorum", "all"] | None = None,
    ) -> bool:
        """Write points to the configured bucket.

        The `points` format matches the InfluxDB v1 client convention:
        ``{"measurement": ..., "tags": {...}, "fields": {...}, "time": ...}``.
        Parameters that are specific to v1 (database, batch_size, consistency)
        are accepted for interface compatibility but ignored.
        """
        _precision_map: dict[str | None, str | None] = {
            "s": "s",
            "m": "ms",
            "ms": "ms",
            "u": "us",
            None: None,
        }
        write_precision = _precision_map.get(time_precision)

        records = []
        for point in points:
            p = influxdb_client.Point(point["measurement"])
            for tag_key, tag_val in point.get("tags", {}).items():
                p = p.tag(tag_key, str(tag_val))
            if tags:
                for tag_key, tag_val in tags.items():
                    p = p.tag(tag_key, str(tag_val))
            for field_key, field_val in point.get("fields", {}).items():
                p = p.field(field_key, field_val)
            if "time" in point:
                p = p.time(point["time"], write_precision)
            records.append(p)

        self._write_api.write(bucket=self.bucket, org=self.org, record=records)
        return True

    def query(
        self,
        measurement: str,
        field: str,
    ) -> dict[str, DatabaseValueType] | None:
        """Return the most recent value of *field* from *measurement*."""
        flux = (
            f'from(bucket: "{escape_quotes(self.bucket)}")\n'
            f"  |> range(start: 0)\n"
            f'  |> filter(fn: (r) => r._measurement == "{escape_quotes(measurement)}")\n'
            f'  |> filter(fn: (r) => r._field == "{escape_quotes(field)}")\n'
            f"  |> last()"
        )
        try:
            tables = self._query_api.query(flux, org=self.org)
            for table in tables:
                for record in table.records:
                    return {"time": str(record.get_time()), field: record.get_value()}
        except Exception:
            logger.exception("Error querying InfluxDB v2 for field %s", field)
        return None

    def query_last(
        self,
        measurement: str,
        namespace: str | None = None,
        before: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        """Return the most recent non-null value of every field in *measurement*."""
        stop_clause = f", stop: {before}" if before is not None else ""
        namespace_filter = (
            f'  |> filter(fn: (r) => r.namespace == "{escape_quotes(namespace)}")\n'
            if namespace is not None
            else ""
        )
        flux = (
            f'from(bucket: "{escape_quotes(self.bucket)}")\n'
            f"  |> range(start: 0{stop_clause})\n"
            f'  |> filter(fn: (r) => r._measurement == "{escape_quotes(measurement)}")\n'
            f"{namespace_filter}"
            f"  |> last()"
        )
        try:
            tables = self._query_api.query(flux, org=self.org)
            return {
                record.get_field(): record.get_value()
                for table in tables
                for record in table.records
                if record.get_value() is not None
            }
        except Exception:
            logger.exception("Error querying InfluxDB v2 measurement %s", measurement)
            return {}

    def get_field_keys(self, measurement: str) -> list[str]:
        """Return all field names present in *measurement*."""
        flux = (
            f'import "influxdata/influxdb/schema"\n'
            f"schema.measurementFieldKeys(\n"
            f'  bucket: "{escape_quotes(self.bucket)}",\n'
            f'  measurement: "{escape_quotes(measurement)}"\n'
            f")"
        )
        try:
            tables = self._query_api.query(flux, org=self.org)
            return [
                str(record.get_value()) for table in tables for record in table.records
            ]
        except Exception:
            logger.exception(
                "Error fetching field keys from InfluxDB v2 measurement %s", measurement
            )
            return []
