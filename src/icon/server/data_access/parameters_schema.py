"""Definition and detection of the parameter storage schema in InfluxDB.

Two schemas are supported:

- **v1**: one field key per parameter (the full identifier), stored in the
  configured measurement.
- **v2**: type-specific value fields, stored in a measurement derived from the configured
  one with an ``icon|v2|`` prefix.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import InfluxDBv1Session

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType

# A legacy parameter field key always contains the namespace specifier.
_IDENTIFIER_MARKER = "namespace='"

# Since V2, we prefix the configured measurement name
V2_MEASUREMENT_PREFIX = "icon|v2|"


# Field keys which hold the values inside influxdb. One per data type.
class FieldKey(str, Enum):
    FLOAT = "value_float"
    INT = "value_int"
    STR = "value_str"
    BOOL = "value_bool"


FIELD_KEY_NAMES = tuple(field.value for field in FieldKey)


def field_key_from_value(value: DatabaseValueType) -> str:
    """Return the type-specific v2 field key for a given value."""
    if isinstance(value, bool):
        return FieldKey.BOOL.value
    if isinstance(value, int):
        return FieldKey.INT.value
    if isinstance(value, float):
        return FieldKey.FLOAT.value
    return FieldKey.STR.value


class ParameterDBSchema(str, Enum):
    PRISTINE = "pristine"
    V1 = "v1"
    V2 = "v2"


def v2_measurement_name(base_measurement: str) -> str:
    """Return the v2 measurement name derived from a base measurement name."""
    if base_measurement.startswith(V2_MEASUREMENT_PREFIX):
        return base_measurement
    return f"{V2_MEASUREMENT_PREFIX}{base_measurement}"


def detect_schema(field_keys: list[str]) -> ParameterDBSchema | None:
    """Classify a measurement's schema from its field keys."""
    keys = set(field_keys)
    if not keys:
        return None
    if keys <= set(FIELD_KEY_NAMES):
        return ParameterDBSchema.V2
    if all(_IDENTIFIER_MARKER in key for key in keys):
        return ParameterDBSchema.V1
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

       - :attr:`ParameterDBSchema.V2`: the ``icon|v2|`` prefixed measurement exists.
       - :attr:`ParameterDBSchema.V1`: the configured measurement exists and uses the
         legacy field-per-parameter schema.
       - :attr:`ParameterDBSchema.PRISTINE`: neither exists.

    Args:
        wrap_connection_errors: When ``True`` (the CLI default), connection failures are
            wrapped in ``AssertionError`` for a friendly message. When ``False`` (used by
            the server), the native ``requests`` / ``urllib3`` exceptions propagate so the
            existing "InfluxDB not available, retrying" logic keeps working.

    Raises:
        AssertionError: if the database is missing or a parameter measurement exists with
            an unexpected schema (and, when wrapping is enabled, on connection failure).
    """
    influx = get_config().databases.influxdbv1
    base_measurement = influx.measurement
    v2_name = v2_measurement_name(base_measurement)

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

        if v2_name in measurements:
            _assert_schema(session, v2_name, ParameterDBSchema.V2)
            return ParameterDBSchema.V2

        if base_measurement in measurements:
            _assert_schema(session, base_measurement, ParameterDBSchema.V1)
            return ParameterDBSchema.V1

    return ParameterDBSchema.PRISTINE
