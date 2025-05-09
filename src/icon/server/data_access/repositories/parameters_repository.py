import json
import logging
from typing import Any

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb import InfluxDBSession, Record
from icon.server.data_access.db_context.influxdb_v1 import (
    DatabaseValueType,
    InfluxDBv1Session,
)
from icon.server.data_access.db_context.valkey import ValkeySession

logger = logging.getLogger(__name__)

ValkeyValueType = bytes | str | float


def get_specifiers_from_parameter_identifier(
    parameter_identifier: str,
) -> tuple[str, str, dict[str, str]]:
    import re

    # Regex pattern to match key='value' pairs, including namespace and parameter_group
    pattern = re.compile(r"(\w+)='([^']*)'")
    matches = pattern.findall(parameter_identifier)

    # Construct the dictionary from the matched key-value pairs
    specifiers = dict(matches)

    # Pop namespace and parameter_group
    namespace = specifiers.pop("namespace")
    parameter_group = specifiers.pop("parameter_group")

    return namespace, parameter_group, specifiers


class ParametersRepository:
    @staticmethod
    async def get_valkey_parameters() -> dict[str, ValkeyValueType]:
        async with ValkeySession() as valkey:
            params_serialized = await valkey.hgetall("parameters")  # type: ignore
        return {key: json.loads(value) for key, value in params_serialized.items()}

    @staticmethod
    async def get_valkey_parameter_by_id(parameter_id: str) -> ValkeyValueType:
        async with ValkeySession() as valkey:
            return await valkey.hget("parameters", key=parameter_id)  # type: ignore

    @staticmethod
    async def update_valkey_parameters(
        parameter_mapping: dict[str, ValkeyValueType],
    ) -> None:
        async with ValkeySession() as valkey:
            await valkey.hset("parameters", mapping=parameter_mapping)  # type: ignore

    @staticmethod
    async def update_valkey_parameter_by_id(
        parameter_id: str, new_value: ValkeyValueType
    ) -> None:
        await ParametersRepository.update_valkey_parameters(
            parameter_mapping={parameter_id: new_value}
        )

    @staticmethod
    def get_influxdbv1_parameters() -> dict[str, DatabaseValueType]:
        with InfluxDBv1Session() as influxdbv1:
            return influxdbv1.query_all(get_config().databases.influxdbv1.measurement)

    @staticmethod
    def get_influxdbv1_parameter_by_id(parameter_id: str) -> DatabaseValueType | None:
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
    def update_influxdbv1_parameters(
        parameter_mapping: dict[str, ValkeyValueType],
    ) -> None:
        records: list[dict[str, Any]] = []

        for parameter_id, value in parameter_mapping.items():
            _, _, specifiers = get_specifiers_from_parameter_identifier(parameter_id)

            records.append(
                {
                    "measurement": get_config().databases.influxdbv1.measurement,
                    "tags": specifiers,
                    "fields": {parameter_id: value},
                }
            )

        with InfluxDBv1Session() as influxdb:
            influxdb.write_points(points=records)

    @staticmethod
    def update_influxdbv1_parameter_by_id(parameter_id: str, value: Any) -> None:
        return ParametersRepository.update_influxdbv1_parameters(
            parameter_mapping={parameter_id: value}
        )

    @staticmethod
    def get_influxdb_parameters() -> list[Record]:
        with InfluxDBSession() as influxdb:
            return influxdb.query_last(bucket=get_config().databases.influxdb.bucket)

    @staticmethod
    def get_influxdb_parameter_by_id(parameter_id: str) -> Record:
        namespace, parameter_group, specifiers = (
            get_specifiers_from_parameter_identifier(parameter_id)
        )
        with InfluxDBSession() as influxdb:
            return influxdb.query_last(
                bucket=get_config().databases.influxdb.bucket,
                measurement=f"{namespace}: {parameter_group}",
                fields={"value"},
                tags=specifiers,
            )[-1]

    @staticmethod
    def update_influxdb_parameters(
        parameter_mapping: dict[str, ValkeyValueType],
    ) -> None:
        records: list[dict[str, Any]] = []

        for parameter_id, value in parameter_mapping.items():
            namespace, parameter_group, specifiers = (
                get_specifiers_from_parameter_identifier(parameter_id)
            )

            records.append(
                {
                    "measurement": f"{namespace}: {parameter_group}",
                    "tags": specifiers,
                    "fields": {"value": value},
                }
            )

        with InfluxDBSession() as influxdb:
            influxdb.write(
                bucket=get_config().databases.influxdb.bucket, record=records
            )

    @staticmethod
    def update_influxdb_parameter_by_id(parameter_id: str, value: Any) -> None:
        return ParametersRepository.update_influxdb_parameters(
            parameter_mapping={parameter_id: value}
        )

    @staticmethod
    def get_ionpulse_parameter_by_id(parameter_id: str) -> Any:
        import tiqi_plugin

        client = tiqi_plugin.Client(
            get_config().ionpulse_plugin.host,
            get_config().ionpulse_plugin.rpc_port,
            client_type="rpc",
        )

        return client.get_parameter_by_id(parameter_id)  # type: ignore

    @staticmethod
    def update_ionpulse_parameters(
        parameter_mapping: dict[str, ValkeyValueType],
    ) -> None:
        import tiqi_plugin

        client = tiqi_plugin.Client(
            get_config().ionpulse_plugin.host,
            get_config().ionpulse_plugin.rpc_port,
            client_type="rpc",
        )

        for parameter_id, value in parameter_mapping.items():
            client.update_parameter_by_id(parameter_id, value)  # type: ignore

    @staticmethod
    def update_ionpulse_parameter_by_id(parameter_id: str, value: Any) -> None:
        return ParametersRepository.update_ionpulse_parameters(
            parameter_mapping={parameter_id: value}
        )
