from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from icon.server.data_access.db_context.influxdb.parameters_backend import (
    InfluxDBParameterBackend,
    assert_parameter_db,
    create_parameter_backend,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

    from icon.config.latest import InfluxDBv1Config
    from icon.server.data_access.experiment_data import DatabaseValueType

logger = logging.getLogger(__name__)


class NotInitialisedError(Exception):
    """Raised when repository methods are called before initialization."""


class ParametersRepository:
    """Repository for parameter values and metadata.

    Provides methods to read and update shared parameter state (via a
    `multiprocessing.Manager` dict) and to persist/retrieve parameters from InfluxDB.
    Emits Socket.IO events on updates.
    """

    def __init__(
        self,
        *,
        shared_parameters: DictProxy[str, DatabaseValueType],
        influx_config: InfluxDBv1Config,
    ) -> None:
        self._shared_parameters = shared_parameters
        self._influx_config = influx_config
        self.initialised = False
        """Set once the initial InfluxDB read has completed; failed initialisation
        attempts can be retried until then."""
        self._backend: InfluxDBParameterBackend | None = None

    def _get_backend(self) -> InfluxDBParameterBackend:
        """Return the schema-specific influxDB parameter backend."""
        if self._backend is None:
            schema_revision = assert_parameter_db(
                self._influx_config, wrap_connection_errors=False
            )
            self._backend = create_parameter_backend(
                schema_revision, self._influx_config
            )
            logger.info(
                "Detected InfluxDB parameter schema %s; using %s.",
                schema_revision.value,
                type(self._backend).__name__,
            )
        return self._backend

    def initialise(self) -> None:
        """Load existing parameters from InfluxDB into the shared parameters dict.

        Marks the repository as initialised. Raises while InfluxDB is
        unreachable, so the caller can retry.
        """
        self._shared_parameters.update(self.get_influxdb_parameters())
        self.initialised = True
        logger.info("ParametersRepository successfully initialised.")

    def _check_initialised(self) -> None:
        """Raise if repository is not initialized."""
        if not self.initialised:
            raise NotInitialisedError("ParametersRepository is not initialised.")

    def update_parameters(
        self,
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

        self._update_shared_parameters(parameter_mapping=parameter_mapping)
        self._update_influxdb_parameters(parameter_mapping=parameter_mapping)

    def _update_shared_parameters(
        self,
        *,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Update multiple parameters in shared state.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """
        for key, value in parameter_mapping.items():
            self._update_shared_parameter_by_id(parameter_id=key, new_value=value)

    def _update_shared_parameter_by_id(
        self,
        *,
        parameter_id: str,
        new_value: DatabaseValueType,
    ) -> None:
        """Update a single parameter value in shared state and emit an event.

        Args:
            parameter_id: ID of the parameter.
            new_value: New value to assign.
        """
        self._check_initialised()

        self._shared_parameters[parameter_id] = new_value

        emit_queue.put(
            {
                "event": "parameter.update",
                "data": {"id": parameter_id, "value": new_value},
            }
        )

    def get_shared_parameter_by_id(
        self,
        *,
        parameter_id: str,
    ) -> DatabaseValueType | None:
        """Return a single parameter value from shared state.

        Args:
            parameter_id: ID of the parameter.

        Returns:
            The parameter value, or None if not set.
        """
        self._check_initialised()

        return self._shared_parameters.get(parameter_id, None)

    def get_shared_parameters(self) -> DictProxy[str, DatabaseValueType]:
        """Return the full shared parameter dictionary.

        Returns:
            Proxy dictionary of parameters.
        """
        self._check_initialised()

        return self._shared_parameters

    def get_influxdb_parameter_keys(self) -> list[str]:
        """Return all known parameter identifiers from InfluxDB."""
        return self._get_backend().get_influxdb_parameter_keys()

    def get_influxdb_parameters(
        self,
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
        return self._get_backend().get_influxdb_parameters(
            before=before, namespace=namespace, measurement=measurement
        )

    def get_influxdb_parameter_by_id(
        self, parameter_id: str
    ) -> DatabaseValueType | None:
        """Return a single parameter value from InfluxDB.

        Args:
            parameter_id: ID of the parameter.

        Returns:
            The parameter value, or None if not found.
        """
        backend = self._get_backend()
        value = backend.get_influxdb_parameter_by_id(parameter_id)
        if value is None:
            logger.error(
                "Could not find parameter with id %s in measurement %s",
                parameter_id,
                backend.measurement,
            )
            return None
        return value

    def _update_influxdb_parameters(
        self,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Write multiple parameter values into InfluxDB.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """
        self._get_backend().update_influxdb_parameters(parameter_mapping)
