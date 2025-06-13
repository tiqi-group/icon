import logging
from typing import Any

import pydase

from icon.server.data_access.repositories.experiment_metadata_repository import (
    ExperimentDict,
    ExperimentMetadataRepository,
)

logger = logging.getLogger(__name__)


class ExperimentsController(pydase.DataService):
    async def get_experiments(self) -> ExperimentDict:
        return await ExperimentMetadataRepository.get_experiment_metadata()

    async def _update_experiment_metadata(
        self, experiment_metadata: dict[str, Any]
    ) -> None:
        logger.debug("Updating experiment metadata...")

        await ExperimentMetadataRepository.update_experiment_metadata(
            new_experiment_metadata=experiment_metadata
        )
