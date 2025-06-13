from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any, Literal, TypedDict, overload

from icon.server.data_access.db_context.valkey import AsyncValkeySession
from icon.server.exceptions import ValkeyUnavailableError
from icon.server.utils.socketio_manager import emit_event
from icon.server.utils.valkey import is_valkey_available

if TYPE_CHECKING:
    from icon.server.data_access.repositories.parameter_metadata_repository import (
        ParameterMetadata,
    )


logger = logging.getLogger(__name__)


class ExperimentMetadata(TypedDict):
    class_name: str
    constructor_kwargs: dict[str, Any]
    parameters: dict[str, dict[str, ParameterMetadata]]


ExperimentDict = dict[str, dict[str, ExperimentMetadata]]


# TODO: This is also used elsewhere - move this to utils!
def get_added_removed_and_updated_keys(
    new_dict: dict[str, Any], cached_dict: dict[str, Any]
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
    @overload
    async def get_experiment_metadata(
        *, deserialize: Literal[True] = True
    ) -> ExperimentDict: ...

    @staticmethod
    @overload
    async def get_experiment_metadata(
        *, deserialize: Literal[False] = False
    ) -> dict[str, str]: ...

    @staticmethod
    async def get_experiment_metadata(
        *, deserialize: bool = True
    ) -> dict[str, str] | ExperimentDict:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        async with AsyncValkeySession() as valkey:
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
    ) -> None:
        if not is_valkey_available():
            raise ValkeyUnavailableError()

        cached_experiment_metadata_serialized = (
            await ExperimentMetadataRepository.get_experiment_metadata(
                deserialize=False
            )
        )

        new_experiment_metadata_serialized = {
            key: json.dumps(value) for key, value in new_experiment_metadata.items()
        }

        async with AsyncValkeySession() as valkey:
            await valkey.hset("experiments", mapping=new_experiment_metadata_serialized)  # type: ignore

            added_exps, removed_exps, updated_exps = get_added_removed_and_updated_keys(
                new_experiment_metadata,
                cached_experiment_metadata_serialized,
            )

            if remove_unspecified and removed_exps:
                await valkey.hdel("experiments", *removed_exps)  # type: ignore

        if removed_exps:
            emit_event(logger=logger, event="experiments.remove", data=removed_exps)

        if added_exps or updated_exps:
            emit_event(
                logger=logger,
                event="experiments.update",
                data={
                    key: new_experiment_metadata[key]
                    for key in set(added_exps) | set(updated_exps)
                },
            )
