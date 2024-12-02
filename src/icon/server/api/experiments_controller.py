import asyncio
import json
import logging

import pydase
from pydase.task.decorator import task

from icon.config import get_config
from icon.server.data_access.db_context.valkey import ValkeySession
from icon.server.data_access.repositories.experiments_repository import (
    ExperimentsRepository,
)

logger = logging.getLogger(__file__)


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


class ExperimentsController(pydase.DataService):
    async def get_experiments(self) -> dict[str, str]:
        async with ValkeySession() as valkey:
            experiments_serialized = await valkey.hgetall("experiments")  # type: ignore
            return {
                key: json.loads(value) for key, value in experiments_serialized.items()
            }

    @task(autostart=True)
    async def _update_experiment_cache(self) -> None:
        while True:
            await self._update_experiment_metadata()
            await asyncio.sleep(get_config().experiment_library.update_interval)

    async def _update_experiment_metadata(self) -> None:
        logger.debug("Updating experiment metadata...")

        current_experiments = await ExperimentsRepository.get_experiments()
        current_experiments_serialized = {
            key: json.dumps(value, sort_keys=True)
            for key, value in current_experiments.items()
        }

        async with ValkeySession() as valkey:
            cached_experiments = await valkey.hgetall("experiments")  # type: ignore
            await valkey.hset("experiments", mapping=current_experiments_serialized)  # type: ignore

            added_exps, removed_exps, updated_exps = get_added_removed_and_updated_keys(
                current_experiments_serialized, cached_experiments
            )
            if removed_exps:
                await valkey.hdel("experiments", *removed_exps)  # type: ignore
