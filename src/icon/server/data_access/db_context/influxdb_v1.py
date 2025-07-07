from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, Literal

import requests

import influxdb
from icon.config.config import get_config

if TYPE_CHECKING:
    from types import TracebackType

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

logger = logging.getLogger(__name__)


DatabaseValueType = bool | float | int | str


def escape_quotes(value: str) -> str:
    """Escape double quotes and single quotes with backslashes."""
    return value.replace("\\", "\\\\").replace('"', r"\"")


def is_responsive() -> bool:
    success = 200

    params = {
        "u": f"{get_config().databases.influxdbv1.username}",
        "p": f"{get_config().databases.influxdbv1.password}",
        "q": "SHOW DATABASES",
    }

    url = (
        f"http{'s' if get_config().databases.influxdbv1.ssl else ''}://"
        f"{get_config().databases.influxdbv1.host}:"
        f"{get_config().databases.influxdbv1.port}/query"
    )

    try:
        response = requests.get(url, params=params)
    except Exception:
        return False
    return (
        response.status_code == success
        and f'["{get_config().databases.influxdbv1.database}"]' in response.text
    )


class InfluxDBv1Session:
    """
    The `InfluxDBv1Session` class serves as a context manager for a connection
    to an InfluxDBv1 server. This connection is established using credentials loaded
    through the ICON configuration file.

    Example:
        ```python
        with InfluxDBv1Session() as influx_client:
            # Writing data to a database
            points = [
                {
                    "measurement": "your_measurement",  # Replace with your measurement
                    "tags": {
                        "example_tag": "tag_value",  # Replace with your tag and value
                    },
                    "fields": {
                        "example_field": 123,  # Replace with your field and its value
                    },
                    "time": "2023-06-05T00:00:00Z",  # Replace with your timestamp
                }
            ]
            influx_client.write_points(points=points, database="other_database")
        ```
    """

    def __init__(self) -> None:
        self._config = get_config().databases.influxdbv1
        self._client: influxdb.InfluxDBClient
        self._host = self._config.host
        self._port = self._config.port
        self._username = self._config.username
        self._password = self._config.password
        self._ssl = self._config.ssl
        self._verify_ssl = self._config.verify_ssl
        self._headers = self._config.headers
        self.database = self._config.database

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

    def disconnect(self) -> None:
        """Close the active connection to the InfluxDB server."""

        self._client.close()

    def connect(self) -> None:
        """Establish a new connection to the InfluxDB server using provided
        credentials."""

        self._client = influxdb.InfluxDBClient(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            database=self.database,
            ssl=self._ssl,
            verify_ssl=self._verify_ssl,
        )

    def write_points(  # noqa: PLR0913
        self,
        points: list[dict[str, Any]],
        time_precision: Literal["s", "m", "ms", "u"] | None = None,
        database: str | None = None,
        tags: dict[str, str] | None = None,
        batch_size: int | None = None,
        consistency: Literal["any", "one", "quorum", "all"] | None = None,
    ) -> bool:
        """Write to multiple time series names.

        Args:
            points:
                The list of points to be written in the database.
            time_precision:
                Either 's', 'm', 'ms' or 'u', defaults to None.
            database:
                The database to write the points to. Defaults to the client's current
                database.
            tags:
                A set of key-value pairs associated with each point. Both keys and
                values must be strings. These are shared tags and will be merged with
                point-specific tags. Defaults to None.
            batch_size:
                Value to write the points in batches instead of all at one time. Useful
                for when doing data dumps from one database to another or when doing a
                massive write operation. Defaults to None
            consistency:
                Consistency for the points. One of {'any','one','quorum','all'}.

        Return:
            True, if the operation is successful

        Example:
            ```python
            >>> points = [
            ...     {
            ...         "measurement": "cpu_load_short",
            ...         "tags": {
            ...             "host": "server01",
            ...             "region": "us-west",
            ...         },
            ...         "time": "2009-11-10T23:00:00Z",
            ...         "fields": {
            ...             "value": 0.64,
            ...         },
            ...     }
            ... ]
            >>> with InfluxDBv1Session() as client:
            ...     client.write_points(points=points)
            ```
        """

        return self._client.write_points(
            points=points,
            time_precision=time_precision,
            database=database,
            tags=tags,
            batch_size=batch_size,
            consistency=consistency,
        )

    def query(
        self,
        measurement: str,
        field: str,
    ) -> dict[str, DatabaseValueType] | None:
        """Query the most recent value of a specific field from a given measurement.

        Args:
            measurement: Name of the measurement to query.
            field: Name of the field to retrieve.

        Returns:
            A dictionary containing the latest field value.
        """

        stmt = (
            f'SELECT "{escape_quotes(field)}" FROM '
            f'"{escape_quotes(measurement)!s}" ORDER BY time DESC LIMIT 1'
        )
        try:
            return next(self._client.query(stmt).get_points())  # type: ignore
        except StopIteration:
            return None

    def query_last(
        self,
        measurement: str,
        namespace: str | None = None,
        before: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        """Query the most recent non-null values of all fields from a given measurement.

        Args:
            measurement: Name of the measurement to query.
            namespace: Optional tag filter.
            timestamp: Optional upper bound on the time.

        Returns:
            Dictionary of field names to their latest values.
        """

        clauses = []
        if namespace is not None:
            clauses.append(f"\"namespace\" = '{escape_quotes(namespace)}'")
        if before is not None:
            clauses.append(f"time <= '{before}'")

        where_clause = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        stmt = (
            f'SELECT last(*::field) FROM "{escape_quotes(measurement)}"{where_clause}'
        )

        try:
            return {
                key[5:]: value  # removes "last_" from the beginning of each key
                for key, value in next(self._client.query(stmt).get_points()).items()  # type: ignore
                if key != "time"  # exclude "time" key which is meaningless
                and value is not None
            }
        except StopIteration:
            return {}

    def get_field_keys(self, measurement: str) -> list[str]:
        """Return list of field names from a measurement."""

        stmt = f'SHOW FIELD KEYS FROM "{escape_quotes(measurement)}"'
        result = list(self._client.query(stmt).get_points())  # type: ignore
        return [row["fieldKey"] for row in result]
