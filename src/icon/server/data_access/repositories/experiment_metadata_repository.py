import json
from typing import Any

from icon.server.data_access.db_context.valkey import ValkeySession


def get_added_removed_and_updated_keys(
    new_dict: dict[str, str], cached_dict: dict[str, str]
) -> tuple[list[str], list[str], list[str]]:
    keys1 = set(cached_dict)
    keys2 = set(new_dict)

    added_keys = keys2 - keys1
    removed_keys = keys1 - keys2

    intersect_keys = keys1 & keys2
    updated_keys = {key for key in intersect_keys if new_dict[key] != cached_dict[key]}

    return list(added_keys), list(removed_keys), list(updated_keys)


class ExperimentMetadataRepository:
    @staticmethod
    async def get_experiment_metadata(*, deserialize: bool = True) -> dict[str, str]:
        async with ValkeySession() as valkey:
            experiments_serialized = await valkey.hgetall("experiments")  # type: ignore

            if deserialize:
                return {
                    key: json.loads(value)
                    for key, value in experiments_serialized.items()
                }
            return experiments_serialized

    @staticmethod
    async def update_experiment_metadata(
        *, new_experiment_metadata: dict[str, Any], remove_unspecified: bool = True
    ) -> tuple[list[str], list[str], list[str]]:
        cached_experiment_metadata_serialized = (
            await ExperimentMetadataRepository.get_experiment_metadata(
                deserialize=False
            )
        )
        async with ValkeySession() as valkey:
            await valkey.hset(
                "experiments", mapping=cached_experiment_metadata_serialized
            )  # type: ignore

            added_exps, removed_exps, updated_exps = get_added_removed_and_updated_keys(
                new_experiment_metadata,
                cached_experiment_metadata_serialized,
            )

            if remove_unspecified and removed_exps:
                await valkey.hdel("experiments", *removed_exps)  # type: ignore

        return added_exps, removed_exps, updated_exps
