from __future__ import annotations

import logging
from typing import TYPE_CHECKING, ClassVar

from icon.server.data_access.db_context.influxdb.parameters_backend import (
    InfluxDBParameterBackend,
    assert_parameter_db,
    create_parameter_backend,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

    from icon.server.data_access.db_context.influxdb.influxdb_v1 import (
        DatabaseValueType,
    )

logger = logging.getLogger(__name__)


class NotInitialisedError(Exception):
    """Raised when repository methods are called before initialization."""


class ParametersRepository:
    """Repository for parameter values and metadata.

    Provides methods to read and update shared parameter state (via a
    `multiprocessing.Manager` dict) and to persist/retrieve parameters from InfluxDB.
    Emits Socket.IO events on updates.
    """

    _shared_parameters: DictProxy[str, DatabaseValueType]
    initialised: bool = False
    _backend: ClassVar[InfluxDBParameterBackend | None] = None

    @classmethod
    def _get_backend(cls) -> InfluxDBParameterBackend:
        """Return the schema-specific influxDB parameter backend."""
        if cls._backend is None:
            version = assert_parameter_db(wrap_connection_errors=False)
            cls._backend = create_parameter_backend(version)
            logger.info(
                "Detected InfluxDB parameter schema %s; using %s.",
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
