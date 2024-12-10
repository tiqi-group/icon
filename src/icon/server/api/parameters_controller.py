import logging
from typing import Any

import pydase

from icon.server.data_access.repositories.parameter_metadata_repository import (
    ParameterMetadata,
    ParameterMetadataRepository,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)

logger = logging.getLogger(__name__)


class ParametersController(pydase.DataService):
    async def get_parameter_metadata(self) -> dict[str, ParameterMetadata]:
        return await ParameterMetadataRepository.get_parameter_metadata()

    async def get_display_groups(
        self,
    ) -> dict[str, dict[str, ParameterMetadata]]:
        return await ParameterMetadataRepository.get_display_groups()

    async def update_parameter_by_id(self, parameter_id: str, value: Any) -> None:
        ParametersRepository.update_ionpulse_parameter_by_id(
            parameter_id=parameter_id, value=value
        )

    async def get_parameter_by_id(self, parameter_id: str) -> Any:
        return ParametersRepository.get_ionpulse_parameter_by_id(
            parameter_id=parameter_id
        )

    async def _update_parameter_metadata_and_display_groups(
        self, parameter_metadata: dict[str, Any]
    ) -> None:
        logger.debug("Updating parameter metadata...")

        (
            added_params,
            removed_params,
            updated_params,
        ) = await ParameterMetadataRepository.update_parameter_metadata(
            new_parameter_metadata=parameter_metadata["all parameters"]
        )
        (
            added_groups,
            removed_groups,
            updated_groups,
        ) = await ParameterMetadataRepository.update_display_groups(
            new_display_groups=parameter_metadata["display groups"]
        )

        # TODO: emit events for changed params and groups
