import asyncio
import logging
from typing import ClassVar

import pydase
from pydase.task.decorator import task

from icon.config import get_config
from icon.server.api.models.experiment import Experiment
from icon.server.data_access.repositories.experiments_repository import (
    ExperimentsRepository,
)

logger = logging.getLogger(__file__)


class ExperimentsController(pydase.DataService):
    _experiments: ClassVar[list[Experiment]] = []

    def get_experiments(self) -> list[Experiment]:
        return self._experiments

    @task(autostart=True)
    async def _update_experiment_cache(self) -> None:
        while True:
            await self._update_experiment_metadata()
            await asyncio.sleep(get_config().experiment_library.update_interval)

    async def _update_experiment_metadata(self) -> None:
        await ExperimentsRepository.get_experiments()
