import logging
from typing import Any

import pydase

from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.repositories.parameter_metadata_repository import (
    ParameterMetadata,
    ParameterMetadataRepository,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.repositories.pycrystal_library_repository import (
    ParameterMetadataDict,
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
        ParametersRepository.update_parameters(parameter_mapping={parameter_id: value})

    async def get_all_parameters(
        self,
    ) -> dict[str, DatabaseValueType]:
        return dict(ParametersRepository.get_shared_parameters())

    async def _update_parameter_metadata_and_display_groups(
        self, parameter_metadata: ParameterMetadataDict
    ) -> None:
        logger.debug("Updating parameter metadata...")

        await ParameterMetadataRepository.update_parameter_metadata(
            new_parameter_metadata=parameter_metadata["all parameters"]
        )
        await ParameterMetadataRepository.update_display_groups(
            new_display_groups=parameter_metadata["display groups"]
        )

    async def _create_missing_influxdb_entries(
        self, parameter_metadata: ParameterMetadataDict
    ) -> None:
        influxdb_param_keys = ParametersRepository.get_influxdbv1_parameter_keys()
        for key, metadata in parameter_metadata["all parameters"].items():
            if key not in influxdb_param_keys:
                logger.info("Creating entry %s: %s", key, metadata["default_value"])
                await self.update_parameter_by_id(key, metadata["default_value"])
