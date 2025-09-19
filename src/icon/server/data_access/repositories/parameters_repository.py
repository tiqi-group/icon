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
    pass


def get_specifiers_from_parameter_identifier(
    parameter_identifier: str,
) -> dict[str, str]:
    # Regex pattern to match key='value' pairs, including namespace and parameter_group
    pattern = re.compile(r"(\w+)='([^']*)'")
    matches = pattern.findall(parameter_identifier)

    return dict(matches)


class ParametersRepository:
    _shared_parameters: DictProxy[str, DatabaseValueType]
    initialised: bool = False

    @classmethod
    def initialize(
        cls, *, shared_parameters: DictProxy[str, DatabaseValueType]
    ) -> None:
        cls._shared_parameters = shared_parameters
        cls.initialised = True

    @classmethod
    def _check_initialised(cls) -> None:
        if not cls.initialised:
            raise NotInitialisedError("ParametersRepository is not initialised.")

    @classmethod
    def update_parameters(
        cls,
        *,
        parameter_mapping: dict[str, DatabaseValueType],
    ) -> None:
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
        for key, value in parameter_mapping.items():
            cls._update_shared_parameter_by_id(parameter_id=key, new_value=value)

    @classmethod
    def _update_shared_parameter_by_id(
        cls,
        *,
        parameter_id: str,
        new_value: DatabaseValueType,
    ) -> None:
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
        cls._check_initialised()

        return cls._shared_parameters.get(parameter_id, None)

    @classmethod
    def get_shared_parameters(cls) -> DictProxy[str, DatabaseValueType]:
        cls._check_initialised()

        return cls._shared_parameters

    @staticmethod
    def get_influxdb_parameter_keys() -> list[str]:
        with InfluxDBv1Session() as influxdbv1:
            return influxdbv1.get_field_keys(
                get_config().databases.influxdbv1.measurement
            )

    @staticmethod
    def get_influxdb_parameters(
        *, before: str | None = None, namespace: str | None = None
    ) -> dict[str, DatabaseValueType]:
        with InfluxDBv1Session() as influxdbv1:
            return influxdbv1.query_last(
                get_config().databases.influxdbv1.measurement,
                before=before,
                namespace=namespace,
            )

    @staticmethod
    def get_influxdb_parameter_by_id(parameter_id: str) -> DatabaseValueType | None:
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
