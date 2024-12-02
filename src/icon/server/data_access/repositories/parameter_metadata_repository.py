import json
from typing import Any

from icon.server.data_access.db_context.valkey import ValkeySession
from icon.server.data_access.repositories.experiment_metadata_repository import (
    get_added_removed_and_updated_keys,
)


class ParameterMetadataRepository:
    @staticmethod
    async def get_parameter_metadata(*, deserialize: bool = True) -> dict[str, str]:
        async with ValkeySession() as valkey:
            parameter_metadata_serialized = await valkey.hgetall("parameter_metadata")  # type: ignore

            if deserialize:
                return {
                    key: json.loads(value)
                    for key, value in parameter_metadata_serialized.items()
                }
            return parameter_metadata_serialized

    @staticmethod
    async def update_parameter_metadata(
        *, new_parameter_metadata: dict[str, Any], remove_unspecified: bool = True
    ) -> tuple[list[str], list[str], list[str]]:
        cached_parameter_metadata_serialized = (
            await ParameterMetadataRepository.get_parameter_metadata(deserialize=False)
        )

        new_parameter_metadata_serialized = {
            key: json.dumps(value) for key, value in new_parameter_metadata.items()
        }
        async with ValkeySession() as valkey:
            await valkey.hset(
                "parameter_metadata", mapping=new_parameter_metadata_serialized
            )  # type: ignore

            added_exps, removed_exps, updated_exps = get_added_removed_and_updated_keys(
                new_parameter_metadata,
                cached_parameter_metadata_serialized,
            )

            if remove_unspecified and removed_exps:
                await valkey.hdel("parameter_metadata", *removed_exps)  # type: ignore

        return added_exps, removed_exps, updated_exps
