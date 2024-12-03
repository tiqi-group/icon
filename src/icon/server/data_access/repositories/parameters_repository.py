import json

from icon.server.data_access.db_context.valkey import ValkeySession

ValkeyValueType = bytes | str | float


class ParametersRepository:
    @staticmethod
    async def get_parameters() -> dict[str, ValkeyValueType]:
        async with ValkeySession() as valkey:
            params_serialized = await valkey.hgetall("parameters")  # type: ignore
        return {key: json.loads(value) for key, value in params_serialized.items()}

    @staticmethod
    async def get_parameter_by_id(parameter_id: str) -> ValkeyValueType:
        async with ValkeySession() as valkey:
            return await valkey.hget("parameters", key=parameter_id)  # type: ignore

    @staticmethod
    async def update_parameter(parameter_id: str, new_value: ValkeyValueType) -> None:
        await ParametersRepository.update_parameters(
            parameter_mapping={parameter_id: new_value}
        )

    @staticmethod
    async def update_parameters(parameter_mapping: dict[str, ValkeyValueType]) -> None:
        async with ValkeySession() as valkey:
            await valkey.hset("parameters", mapping=parameter_mapping)  # type: ignore

        # TODO: update influxdb
