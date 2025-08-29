import logging
from typing import Any

import pydase

import icon.server.shared_resource_manager
from icon.server.api.models.parameter_metadata import ParameterMetadata
from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.repositories.pycrystal_library_repository import (
    ParameterMetadataDict,
)
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


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


class ParametersController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self._all_parameter_metadata: dict[str, ParameterMetadata] = {}
        self._display_group_metadata: dict[str, dict[str, ParameterMetadata]] = {}

    def update_parameter_by_id(self, parameter_id: str, value: Any) -> None:
        ParametersRepository.update_parameters(parameter_mapping={parameter_id: value})

    def get_all_parameters(
        self,
    ) -> dict[str, DatabaseValueType]:
        return dict(ParametersRepository.get_shared_parameters())

    def get_display_groups(
        self,
    ) -> dict[str, dict[str, ParameterMetadata]]:
        return self._display_group_metadata

    async def _update_parameter_metadata_and_display_groups(
        self, parameter_metadata: ParameterMetadataDict
    ) -> None:
        logger.debug("Updating parameter metadata...")

        added_params, removed_params, updated_params = (
            get_added_removed_and_updated_keys(
                self._all_parameter_metadata, parameter_metadata["all parameters"]
            )
        )
        self._all_parameter_metadata = parameter_metadata["all parameters"]
        self._display_group_metadata = parameter_metadata["display groups"]

        # This does not take into account that the display groups change while all
        # parameter metadata stays the same.
        if added_params or removed_params or updated_params:
            emit_queue.put({"event": "parameters.update", "data": None})

    def _create_missing_influxdb_entries(self) -> None:
        """Ensure all known parameters exist in InfluxDBv1.

        For each parameter in the metadata, check if it exists as a field in InfluxDBv1.
        If not, initialize it by writing the default value via the ParametersRepository.
        """

        influxdb_param_keys = ParametersRepository.get_influxdbv1_parameter_keys()
        for parameter_id, metadata in self._all_parameter_metadata.items():
            if parameter_id not in influxdb_param_keys:
                logger.info(
                    "Creating entry %s: %s", parameter_id, metadata["default_value"]
                )
                self.update_parameter_by_id(parameter_id, metadata["default_value"])

    def initialise_parameters_repository(self) -> None:
        icon.server.shared_resource_manager.parameters_dict.update(
            ParametersRepository.get_influxdbv1_parameters()
        )
        ParametersRepository.initialize(
            shared_parameters=icon.server.shared_resource_manager.parameters_dict
        )
        logger.info("ParametersRepository successfully initialised.")
