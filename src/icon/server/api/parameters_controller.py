import logging
from typing import Any

import pydase

from icon.server.data_access.repositories.parameter_metadata_repository import (
    ParameterMetadataRepository,
)

logger = logging.getLogger(__name__)


class ParametersController(pydase.DataService):
    async def get_experiments(self) -> dict[str, str]:
        return await ParameterMetadataRepository.get_parameter_metadata()

    async def _update_parameter_metadata(
        self, parameter_metadata: dict[str, Any]
    ) -> None:
        logger.debug("Updating parameter metadata...")

        (
            added_exps,
            removed_exps,
            updated_exps,
        ) = await ParameterMetadataRepository.update_parameter_metadata(
            new_parameter_metadata=parameter_metadata
        )
