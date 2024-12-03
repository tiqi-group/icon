import logging
from typing import Any

import pydase

from icon.server.data_access.repositories.experiment_metadata_repository import (
    ExperimentMetadataRepository,
)

logger = logging.getLogger(__name__)



class ExperimentsController(pydase.DataService):
    async def get_experiments(self) -> dict[str, str]:
        return await ExperimentMetadataRepository.get_experiment_metadata()

    async def _update_experiment_metadata(
        self, experiment_metadata: dict[str, Any]
    ) -> None:
        logger.debug("Updating experiment metadata...")

        (
            added_exps,
            removed_exps,
            updated_exps,
        ) = await ExperimentMetadataRepository.update_experiment_metadata(
            new_experiment_metadata=experiment_metadata
        )
