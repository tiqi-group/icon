"""Definition and detection of the parameter storage schema in InfluxDB.

Two schema revisions are supported:

- **r1**: one field key per parameter (the full identifier), stored in the
  configured measurement.
- **r2**: type-specific value fields, stored in a measurement derived from the configured
  one with an ``icon|2|`` prefix.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, Any

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
    InfluxDBSessionProvider,
    InfluxDBv1Session,
    default_session_provider,
    escape_quotes,
    escape_tag_value,
)

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
        DatabaseValueType,
    )

# A legacy parameter field key always contains the namespace specifier.
_IDENTIFIER_MARKER = "namespace='"

# Since r2, we prefix the configured measurement name
_R2_MEASUREMENT_PREFIX = "icon|2|"


# Field keys which hold the values inside influxdb. One per data type.
class FieldKey(str, Enum):
    FLOAT = "icon_parameter_value_float"
    INT = "icon_parameter_value_int"
    STR = "icon_parameter_value_str"
    BOOL = "icon_parameter_value_bool"


FIELD_KEY_NAMES = tuple(field.value for field in FieldKey)


def field_key_from_value(value: DatabaseValueType) -> str:
    """Return the per-type r2 field key for a given value."""
    if isinstance(value, bool):
        return FieldKey.BOOL.value
    if isinstance(value, int):
        return FieldKey.INT.value
    if isinstance(value, float):
        return FieldKey.FLOAT.value
    return FieldKey.STR.value


class ParameterDBSchema(str, Enum):
    PRISTINE = "pristine"  # Empty database
    R1 = "r1"
    R2 = "r2"


def r2_measurement_name(base_measurement: str) -> str:
    """Return the r2 measurement name derived from a base measurement name."""
    if base_measurement.startswith(_R2_MEASUREMENT_PREFIX):
        return base_measurement
    return f"{_R2_MEASUREMENT_PREFIX}{base_measurement}"


def detect_schema(field_keys: list[str]) -> ParameterDBSchema | None:
    """Classify a measurement's schema from its field keys."""
    keys = set(field_keys)
    if not keys:
        return None
    if keys <= set(FIELD_KEY_NAMES):
        return ParameterDBSchema.R2
    if any(_IDENTIFIER_MARKER in key for key in keys):
        return ParameterDBSchema.R1
    return None


def _assert_schema(
    session: InfluxDBv1Session,
    measurement: str,
    expected: ParameterDBSchema,
) -> None:
    """Raise ``AssertionError`` unless a measurement's schema matches ``expected``."""
    schema = detect_schema(session.get_field_keys(measurement))
    if schema is not expected:
        found = schema.value if schema is not None else "unrecognised"
        msg = (
            f"Measurement {measurement!r} was expected to use the {expected.value} "
            f"schema but its fields are {found}."
        )
        raise AssertionError(msg)


def assert_parameter_db(*, wrap_connection_errors: bool = True) -> ParameterDBSchema:
    """Assert the parameter database is reachable and return its schema version.

    Determines the schema version from which parameter measurement exists:

       - :attr:`ParameterDBSchema.R2`: the ``icon|2|`` prefixed measurement exists.
       - :attr:`ParameterDBSchema.R1`: the configured measurement exists and uses the
         legacy field-per-parameter schema.
       - :attr:`ParameterDBSchema.PRISTINE`: neither exists.

    Args:
        wrap_connection_errors: When ``True`` (the CLI default), connection failures are
            wrapped in ``AssertionError`` for a friendly message. When ``False`` (used by
            the server), the native ``requests`` / ``urllib3`` exceptions propagate so the
            existing "InfluxDB not available, retrying" logic keeps working.

    Raises:
        AssertionError: if the database is missing or a parameter measurement exists with
            an unexpected schema.
    """
    influx = get_config().databases.influxdbv1
    base_measurement = influx.measurement
    r2_name = r2_measurement_name(base_measurement)

    with InfluxDBv1Session() as session:
        try:
            databases = session.get_databases()
        except Exception as exc:
            if not wrap_connection_errors:
                raise
            msg = f"Could not connect to InfluxDB at {influx.host}:{influx.port}: {exc}"
            raise AssertionError(msg) from exc

        if influx.database not in databases:
            msg = f"Configured InfluxDB database {influx.database!r} does not exist."
            raise AssertionError(msg)

        measurements = set(session.get_measurements())

        if r2_name in measurements:
            _assert_schema(session, r2_name, ParameterDBSchema.R2)
            return ParameterDBSchema.R2

        if base_measurement in measurements:
            _assert_schema(session, base_measurement, ParameterDBSchema.R1)
            return ParameterDBSchema.R1

    return ParameterDBSchema.PRISTINE


_SPECIFIER_KEY_ORDER = ("namespace", "parameter_group", "param_type")


def get_specifiers_from_parameter_identifier(
    parameter_identifier: str,
) -> dict[str, str]:
    """Extract specifiers from a parameter identifier string.

    Parameter identifiers encode metadata as `key='value'` pairs. This helper parses
    them into a dictionary.

    Args:
        parameter_identifier: Identifier string to parse.

    Returns:
        Mapping of specifier keys to values.
    """
    pattern = re.compile(r"(\w+)='([^']*)'")
    matches = pattern.findall(parameter_identifier)

    return dict(matches)


def build_parameter_identifier_from_specifiers(specifiers: dict[str, str]) -> str:
    """Reconstruct a parameter identifier string from its specifiers.

    Inverse of :func:`get_specifiers_from_parameter_identifier`. Keys are emitted in the
    canonical :data:`_SPECIFIER_KEY_ORDER` and any unexpected keys are appended
    in sorted order. Specifiers with an empty value are ignored.

    Args:
        specifiers: Mapping of specifier keys to values.

    Returns:
        The canonical identifier string.
    """
    specifiers = {key: value for key, value in specifiers.items() if value != ""}

    ordered_keys = [key for key in _SPECIFIER_KEY_ORDER if key in specifiers]
    ordered_keys += sorted(key for key in specifiers if key not in _SPECIFIER_KEY_ORDER)

    return " ".join(f"{key}='{specifiers[key]}'" for key in ordered_keys)


def _where_clause(namespace: str | None, before: str | None) -> str:
    """Build the ``WHERE`` clause shared by the schema-wide "latest value" queries."""
    clauses = []
    if namespace is not None:
        clauses.append(f"\"namespace\" = '{escape_tag_value(namespace)}'")
    if before is not None:
        clauses.append(f"time <= '{before}'")
    return f" WHERE {' AND '.join(clauses)}" if clauses else ""


class InfluxDBParameterBackend(ABC):
    """ABC for parameter storage in influxDB."""

    schema: ParameterDBSchema
    measurement: str

    def __init__(self, session_provider: InfluxDBSessionProvider | None = None) -> None:
        self._session_provider = session_provider or default_session_provider

    @abstractmethod
    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        """Return the latest value of every parameter."""

    @abstractmethod
    def get_influxdb_parameter_keys(self) -> list[str]:
        """Return all known parameter identifiers."""

    @abstractmethod
    def get_influxdb_parameter_by_id(
        self, parameter_id: str
    ) -> DatabaseValueType | None:
        """Return the latest value of a single parameter."""

    @abstractmethod
    def _fields_for(
        self, parameter_id: str, value: DatabaseValueType
    ) -> dict[str, DatabaseValueType]:
        """Return the field mapping written for a single parameter/value pair."""

    def update_influxdb_parameters(
        self,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Write multiple parameter values, one point per parameter.

        Args:
            parameter_mapping: Mapping of parameter id to value.
        """
        _measurement = self.measurement
        records: list[dict[str, Any]] = []
        for parameter_id, value in parameter_mapping.items():
            record: dict[str, Any] = {
                "measurement": _measurement,
                "tags": get_specifiers_from_parameter_identifier(parameter_id),
                "fields": self._fields_for(parameter_id, value),
            }
            records.append(record)
        with self._session_provider() as session:
            session.write_points(points=records, time_precision="n")


def value_from_point(point: dict[str, Any]) -> DatabaseValueType | None:
    """Return the single non-null typed value from a queried point, if any."""
    for field in FIELD_KEY_NAMES:
        value = point.get(field)
        if value is not None:
            return value
    return None


class ParameterBackendR2(InfluxDBParameterBackend):
    schema = ParameterDBSchema.R2

    def __init__(self, session_provider: InfluxDBSessionProvider | None = None) -> None:
        self.measurement = r2_measurement_name(
            get_config().databases.influxdbv1.measurement
        )
        super().__init__(session_provider)

    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        stmt = (
            f"SELECT {','.join(FIELD_KEY_NAMES)} "
            f'FROM "{escape_quotes(measurement or self.measurement)}"'
            f"{_where_clause(namespace, before)} GROUP BY *"
            "ORDER BY time DESC LIMIT 1"
        )
        result: dict[str, DatabaseValueType] = {}
        with self._session_provider() as session:
            for (_measurement, tags), points in session.query(stmt).items():
                point: dict[str, DatabaseValueType] = next(iter(points), {})
                value = value_from_point(point)
                if tags and value is not None:
                    identifier = build_parameter_identifier_from_specifiers(dict(tags))
                    result[identifier] = value
        return result

    def get_influxdb_parameter_keys(self) -> list[str]:
        return list(self.get_influxdb_parameters())

    def get_influxdb_parameter_by_id(
        self, parameter_id: str
    ) -> DatabaseValueType | None:
        conditions = " AND ".join(
            f"\"{escape_quotes(key)}\" = '{escape_tag_value(value)}'"
            for key, value in get_specifiers_from_parameter_identifier(
                parameter_id
            ).items()
        )
        where = f" WHERE {conditions}" if conditions else ""
        stmt = (
            f"SELECT {','.join(FIELD_KEY_NAMES)} "
            f'FROM "{escape_quotes(self.measurement)}"{where}'
            "ORDER BY time desc limit 1"
        )
        with self._session_provider() as session:
            point: dict[str, DatabaseValueType] = next(
                session.query(stmt).get_points(), {}
            )
        return value_from_point(point)

    def _fields_for(
        self,
        parameter_id: str,  # noqa: ARG002 - the typed schema keys fields by value type
        value: DatabaseValueType,
    ) -> dict[str, DatabaseValueType]:
        return {field_key_from_value(value): value}


class ParameterBackendR1(InfluxDBParameterBackend):
    schema = ParameterDBSchema.R1

    def __init__(self, session_provider: InfluxDBSessionProvider | None = None) -> None:
        self.measurement = get_config().databases.influxdbv1.measurement
        super().__init__(session_provider)

    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        stmt = (
            f'SELECT last(*::field) FROM "{escape_quotes(measurement or self.measurement)}"'
            f"{_where_clause(namespace, before)}"
        )
        with self._session_provider() as session:
            row: dict[str, DatabaseValueType] = next(
                session.query(stmt).get_points(), {}
            )

        return {
            key[5:]: value  # removes "last_" from the beginning of each key
            for key, value in row.items()
            if key != "time"
            and value is not None  # exclude "time" key which is meaningless
        }

    def get_influxdb_parameter_keys(self) -> list[str]:
        with self._session_provider() as session:
            return session.get_field_keys(self.measurement)

    def get_influxdb_parameter_by_id(
        self, parameter_id: str
    ) -> DatabaseValueType | None:
        stmt = (
            f'SELECT last("{escape_quotes(parameter_id)}") '
            f'FROM "{escape_quotes(self.measurement)}"'
        )
        with self._session_provider() as session:
            point: dict[str, DatabaseValueType] = next(
                session.query(stmt).get_points(), {}
            )
        return point.get("last")

    def _fields_for(
        self, parameter_id: str, value: DatabaseValueType
    ) -> dict[str, DatabaseValueType]:
        return {parameter_id: value}


_BACKENDS: dict[ParameterDBSchema, type[InfluxDBParameterBackend]] = {
    ParameterDBSchema.R1: ParameterBackendR1,
    ParameterDBSchema.R2: ParameterBackendR2,
    # A pristine database is initialised with the current (r2) schema.
    ParameterDBSchema.PRISTINE: ParameterBackendR2,
}


def create_parameter_backend(
    version: ParameterDBSchema, session_provider: InfluxDBSessionProvider | None = None
) -> InfluxDBParameterBackend:
    """Instantiate the parameter backend for a detected schema version."""
    return _BACKENDS[version](session_provider=session_provider)
