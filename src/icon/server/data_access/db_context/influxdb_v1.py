from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any, Literal, cast

import influxdb
import requests

from icon.config.config import get_config

if TYPE_CHECKING:
    from types import TracebackType

    from influxdb.resultset import ResultSet

if sys.version_info < (3, 11):
    from typing_extensions import Self
else:
    from typing import Self

logger = logging.getLogger(__name__)


DatabaseValueType = bool | float | int | str


def escape_quotes(value: str) -> str:
    """Escape backslashes and double quotes for use in a double-quoted identifier."""
    return value.replace("\\", "\\\\").replace('"', r"\"")


def escape_tag_value(value: str) -> str:
    """Escape backslashes and single quotes for use in a single-quoted literal."""
    return value.replace("\\", "\\\\").replace("'", r"\'")


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
        response = requests.get(url, params=params, timeout=1)
    except Exception:
        return False
    return (
        response.status_code == success
        and f'["{get_config().databases.influxdbv1.database}"]' in response.text
    )


class InfluxDBv1Session:
    """The `InfluxDBv1Session` class serves as a context manager for a connection to an InfluxDBv1 server.

    This connection is established using credentials loaded
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
        """Establish a new connection to the InfluxDB server using provided credentials."""
        self._client = influxdb.InfluxDBClient(
            host=self._host,
            port=self._port,
            username=self._username,
            password=self._password,
            database=self.database,
            ssl=self._ssl,
            verify_ssl=self._verify_ssl,
        )

    def write_points(
        self,
        points: list[dict[str, Any]],
        time_precision: Literal["s", "m", "ms", "u", "n"] | None = None,
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
                Either 's', 'm', 'ms', 'u' or 'n', defaults to None.
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

    def query(self, stmt: str, epoch: str | None = None) -> ResultSet:
        """Run a raw InfluxQL query and return its result set.

        This is a thin, schema-agnostic passthrough. Callers use ``.get_points()`` for a
        flat point iterator or ``.items()`` for series grouped by their tags. Schema-aware
        statement construction lives in the parameter repository, not here.

        Args:
            stmt: The InfluxQL statement to execute.
            epoch: Optional time precision for returned timestamps (e.g. ``"ns"``).

        Returns:
            The InfluxDB result set.
        """
        # Non-chunked queries always return a single ResultSet (never a generator).
        return cast("ResultSet", self._client.query(stmt, epoch=epoch))

    def get_field_keys(self, measurement: str) -> list[str]:
        """Return all field keys of a measurement."""
        stmt = f'SHOW FIELD KEYS FROM "{escape_quotes(measurement)}"'
        return [row["fieldKey"] for row in self.query(stmt).get_points()]

    def get_databases(self) -> list[str]:
        """Return the names of all databases on the server."""
        return [db["name"] for db in self._client.get_list_database()]

    def get_measurements(self) -> list[str]:
        """Return the measurement names in the current database."""
        return [m["name"] for m in self._client.get_list_measurements()]
