from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import (
    DatabaseValueType,
    InfluxDBv1Session,
    escape_quotes,
    escape_tag_value,
)
from icon.server.data_access.parameters_schema import (
    FIELD_KEY_NAMES,
    ParameterDBSchema,
    assert_parameter_db,
    field_key_from_value,
    v2_measurement_name,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

logger = logging.getLogger(__name__)


class NotInitialisedError(Exception):
    """Raised when repository methods are called before initialization."""

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


class InfluxDBParameterBackendABC(ABC):
    """ABC for parameter storage in influxDB."""

    @property
    @abstractmethod
    def measurement(self) -> str:
        """The measurement this backend reads from and writes to."""

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

    def update_influxdb_parameters(
        self, parameter_mapping: dict[str, DatabaseValueType]
    ) -> None:
        """Write multiple parameter values, one point per parameter."""
        records: list[dict[str, Any]] = [
            {
                "measurement": self.measurement,
                "tags": get_specifiers_from_parameter_identifier(parameter_id),
                "fields": self._fields_for(parameter_id, value),
            }
            for parameter_id, value in parameter_mapping.items()
        ]
        with InfluxDBv1Session() as session:
            session.write_points(points=records)

    @abstractmethod
    def _fields_for(
        self, parameter_id: str, value: DatabaseValueType
    ) -> dict[str, DatabaseValueType]:
        """Return the field mapping written for a single parameter/value pair."""


def value_from_point(point: dict[str, Any]) -> DatabaseValueType | None:
    """Return the single non-null typed value from a queried point, if any."""
    for field in FIELD_KEY_NAMES:
        value = point.get(field)
        if value is not None:
            return value
    return None

class ParameterBackendV2(InfluxDBParameterBackendABC):
    """v2 schema: one ``value_*`` field per DatabaseValueType with specifiers as tags.

    Measurement is prefixed with ``icon|v2|``. Every series stores its value in
    exactly one of the :data:`FIELD_KEY_NAMES`; ``GROUP BY *`` yields one row per series, and
    the tag set is mapped back to a parameter identifier.
    """

    _SELECT_LAST = ", ".join(f'last("{field}") AS "{field}"' for field in FIELD_KEY_NAMES)

    @property
    def measurement(self) -> str:
        return v2_measurement_name(get_config().databases.influxdbv1.measurement)

    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        stmt = (
            f"SELECT {self._SELECT_LAST} "
            f'FROM "{escape_quotes(measurement or self.measurement)}"'
            f"{_where_clause(namespace, before)} GROUP BY *"
        )
        result: dict[str, DatabaseValueType] = {}
        with InfluxDBv1Session() as session:
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
            f"SELECT {self._SELECT_LAST} "
            f'FROM "{escape_quotes(self.measurement)}"{where}'
        )
        with InfluxDBv1Session() as session:
            point: dict[str, DatabaseValueType] = next(session.query(stmt).get_points(), {})
        return value_from_point(point)

    def _fields_for(
        self,
        parameter_id: str,  # noqa: ARG002 - the typed schema keys fields by value type
        value: DatabaseValueType,
    ) -> dict[str, DatabaseValueType]:
        return {field_key_from_value(value): value}


class ParameterBackendV1(InfluxDBParameterBackendABC):
    """v1 schema: one field key per parameter, in the configured measurement."""

    @property
    def measurement(self) -> str:
        return get_config().databases.influxdbv1.measurement

    def get_influxdb_parameters(
        self,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        # ``last(*::field)`` returns one row whose columns are ``last_<field>`` for every
        # field key (each field key is a full parameter identifier).
        stmt = (
            f'SELECT last(*::field) FROM "{escape_quotes(measurement or self.measurement)}"'
            f"{_where_clause(namespace, before)}"
        )
        with InfluxDBv1Session() as session:
            row : dict[str, DatabaseValueType] = next(session.query(stmt).get_points(), {})

        return {
            key[5:]: value  # removes "last_" from the beginning of each key
            for key, value in row.items()
            if key != "time" and value is not None # exclude "time" key which is meaningless
        }

    def get_influxdb_parameter_keys(self) -> list[str]:
        with InfluxDBv1Session() as session:
            return session.get_field_keys(self.measurement)

    def get_influxdb_parameter_by_id(
        self, parameter_id: str
    ) -> DatabaseValueType | None:
        stmt = (
            f'SELECT "{escape_quotes(parameter_id)}" '
            f'FROM "{escape_quotes(self.measurement)}" ORDER BY time DESC LIMIT 1'
        )
        with InfluxDBv1Session() as session:
            point = next(session.query(stmt).get_points(), None)
        return None if point is None else point.get(parameter_id)

    def _fields_for(
        self, parameter_id: str, value: DatabaseValueType
    ) -> dict[str, DatabaseValueType]:
        return {parameter_id: value}


_BACKENDS: dict[ParameterDBSchema, type[InfluxDBParameterBackendABC]] = {
    ParameterDBSchema.V1: ParameterBackendV1,
    ParameterDBSchema.V2: ParameterBackendV2,
    # A pristine database is initialised with the current (v2) schema.
    ParameterDBSchema.PRISTINE: ParameterBackendV2,
}


def create_parameter_backend(version: ParameterDBSchema) -> InfluxDBParameterBackendABC:
    """Instantiate the parameter backend for a detected schema version."""
    return _BACKENDS[version]()


class ParametersRepository:
    """Repository for parameter values and metadata.

    Provides methods to read and update shared parameter state (via a
    `multiprocessing.Manager` dict) and to persist/retrieve parameters from InfluxDB.
    Emits Socket.IO events on updates.
    """

    _shared_parameters: DictProxy[str, DatabaseValueType]
    initialised: bool = False
    _backend: ClassVar[InfluxDBParameterBackendABC | None] = None

    @classmethod
    def _get_backend(cls) -> InfluxDBParameterBackendABC:
        """Return the schema-specific influxDB parameter backend."""
        if cls._backend is None:
            version = assert_parameter_db(wrap_connection_errors=False)
            cls._backend = create_parameter_backend(version)
            logger.info(
                "Detected %s parameter schema; using %s.",
                version.value,
                type(cls._backend).__name__,
            )
        return cls._backend

    @classmethod
    def initialize(
        cls, *, shared_parameters: DictProxy[str, DatabaseValueType]
    ) -> None:
        """Initialize the repository with a shared parameters dict.

        Args:
            shared_parameters: Proxy dictionary used to store shared state.
        """
        cls._shared_parameters = shared_parameters
        cls.initialised = True

    @classmethod
    def _check_initialised(cls) -> None:
        """Raise if repository is not initialized."""
        if not cls.initialised:
            raise NotInitialisedError("ParametersRepository is not initialised.")

    @classmethod
    def update_parameters(
        cls,
        *,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Update parameters in both shared state and InfluxDB.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """
        for key, value in parameter_mapping.items():
            if (
                isinstance(value, int)
                and not isinstance(value, bool)
                and "ParameterTypes.INT" not in key
            ):
                parameter_mapping[key] = float(value)

        cls._update_shared_parameters(parameter_mapping=parameter_mapping)
        cls._update_influxdb_parameters(parameter_mapping=parameter_mapping)

    @classmethod
    def _update_shared_parameters(
        cls,
        *,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Update multiple parameters in shared state.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """
        for key, value in parameter_mapping.items():
            cls._update_shared_parameter_by_id(parameter_id=key, new_value=value)

    @classmethod
    def _update_shared_parameter_by_id(
        cls,
        *,
        parameter_id: str,
        new_value: DatabaseValueType,
    ) -> None:
        """Update a single parameter in shared state and emit an event.

        Args:
            parameter_id: ID of the parameter.
            new_value: New value to assign.
        """
        cls._check_initialised()

        cls._shared_parameters[parameter_id] = new_value

        emit_queue.put(
            {
                "event": "parameter.update",
                "data": {"id": parameter_id, "value": new_value},
            }
        )

    @classmethod
    def get_shared_parameter_by_id(
        cls,
        *,
        parameter_id: str,
    ) -> DatabaseValueType | None:
        """Return a single parameter value from shared state.

        Args:
            parameter_id: ID of the parameter.

        Returns:
            The parameter value, or None if not set.
        """
        cls._check_initialised()

        return cls._shared_parameters.get(parameter_id, None)

    @classmethod
    def get_shared_parameters(cls) -> DictProxy[str, DatabaseValueType]:
        """Return the full shared parameter dictionary.

        Returns:
            Proxy dictionary of parameters.
        """
        cls._check_initialised()

        return cls._shared_parameters

    @classmethod
    def get_influxdb_parameter_keys(cls) -> list[str]:
        """Return all known parameter identifiers from InfluxDB."""
        return cls._get_backend().get_influxdb_parameter_keys()

    @classmethod
    def get_influxdb_parameters(
        cls,
        *,
        before: str | None = None,
        namespace: str | None = None,
        measurement: str | None = None,
    ) -> dict[str, DatabaseValueType]:
        """Return the latest parameter values from InfluxDB.

        Args:
            before: Optional ISO timestamp to query parameters before.
            namespace: Optional namespace filter.
            measurement: Optional measurement override; defaults to the active backend's
                measurement.

        Returns:
            Mapping of parameter IDs to values.
        """
        return cls._get_backend().get_influxdb_parameters(
            before=before, namespace=namespace, measurement=measurement
        )

    @classmethod
    def get_influxdb_parameter_by_id(
        cls, parameter_id: str
    ) -> DatabaseValueType | None:
        """Return a single parameter value from InfluxDB.

        Args:
            parameter_id: ID of the parameter.

        Returns:
            The parameter value, or None if not found.
        """
        backend = cls._get_backend()
        value = backend.get_influxdb_parameter_by_id(parameter_id)
        if value is None:
            logger.error(
                "Could not find parameter with id %s in measurement %s",
                parameter_id,
                backend.measurement,
            )
            return None
        return value

    @classmethod
    def _update_influxdb_parameters(
        cls,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Write multiple parameter values into InfluxDB.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """
        cls._get_backend().update_influxdb_parameters(parameter_mapping)
