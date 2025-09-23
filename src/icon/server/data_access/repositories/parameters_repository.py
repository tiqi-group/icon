from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb_v1 import (
    DatabaseValueType,
    InfluxDBv1Session,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

if TYPE_CHECKING:
    from multiprocessing.managers import DictProxy

logger = logging.getLogger(__name__)


class NotInitialisedError(Exception):
    """Raised when repository methods are called before initialization."""


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


class ParametersRepository:
    """Repository for parameter values and metadata.

    Provides methods to read and update shared parameter state (via a
    `multiprocessing.Manager` dict) and to persist/retrieve parameters from InfluxDB.
    Emits Socket.IO events on updates.
    """

    _shared_parameters: DictProxy[str, DatabaseValueType]
    initialised: bool = False

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

    @staticmethod
    def get_influxdb_parameter_keys() -> list[str]:
        """Return all parameter field keys from InfluxDB v1."""

        with InfluxDBv1Session() as influxdbv1:
            return influxdbv1.get_field_keys(
                get_config().databases.influxdbv1.measurement
            )

    @staticmethod
    def get_influxdb_parameters(
        *, before: str | None = None, namespace: str | None = None
    ) -> dict[str, DatabaseValueType]:
        """Return the latest parameter values from InfluxDB.

        Args:
            before: Optional ISO timestamp to query parameters before.
            namespace: Optional namespace filter.

        Returns:
            Mapping of parameter IDs to values.
        """

        with InfluxDBv1Session() as influxdbv1:
            return influxdbv1.query_last(
                get_config().databases.influxdbv1.measurement,
                before=before,
                namespace=namespace,
            )

    @staticmethod
    def get_influxdb_parameter_by_id(parameter_id: str) -> DatabaseValueType | None:
        """Return a single parameter value from InfluxDB.

        Args:
            parameter_id: ID of the parameter.

        Returns:
            The parameter value, or None if not found.
        """

        with InfluxDBv1Session() as influxdb:
            result_dict = influxdb.query(
                measurement=get_config().databases.influxdbv1.measurement,
                field=parameter_id,
            )
            if result_dict is None:
                logger.error(
                    "Could not find parameter with id %s in database %s",
                    parameter_id,
                    get_config().databases.influxdbv1.measurement,
                )
                return None
            return result_dict[parameter_id]

    @staticmethod
    def _update_influxdb_parameters(
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
        """Write multiple parameter values into InfluxDB.

        Args:
            parameter_mapping: Mapping of parameter IDs to values.
        """

        records: list[dict[str, Any]] = []

        for parameter_id, value in parameter_mapping.items():
            records.append(
                {
                    "measurement": get_config().databases.influxdbv1.measurement,
                    "tags": get_specifiers_from_parameter_identifier(parameter_id),
                    "fields": {parameter_id: value},
                }
            )

        with InfluxDBv1Session() as influxdb:
            influxdb.write_points(points=records)
