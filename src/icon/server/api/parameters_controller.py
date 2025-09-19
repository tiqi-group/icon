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
    """Compare two dictionaries and return added, removed, and updated keys.

    Args:
        new_dict: The latest dictionary state.
        cached_dict: The previously cached dictionary state.

    Returns:
        A tuple of three lists:

            - added keys
            - removed keys
            - updated keys (present in both but with changed values)
    """

    keys1 = set(cached_dict)
    keys2 = set(new_dict)

    added_keys = keys2 - keys1
    removed_keys = keys1 - keys2

    intersect_keys = keys1 & keys2
    updated_keys = {key for key in intersect_keys if new_dict[key] != cached_dict[key]}

    return list(added_keys), list(removed_keys), list(updated_keys)


class ParametersController(pydase.DataService):
    """Controller for parameter metadata and shared parameter values.

    Maintains metadata for all parameters and their display groups, exposes read/write
    access to parameter value via the API, and ensures parameters are initialized in the
    InfluxDB backend.
    """

    def __init__(self) -> None:
        super().__init__()
        self._all_parameter_metadata: dict[str, ParameterMetadata] = {}
        self._display_group_metadata: dict[str, dict[str, ParameterMetadata]] = {}

    def update_parameter_by_id(self, parameter_id: str, value: Any) -> None:
        """Update a single parameter value in InfluxDB.

        Args:
            parameter_id: The unique identifier of the parameter.
            value: The new value to assign.
        """

        ParametersRepository.update_parameters(parameter_mapping={parameter_id: value})

    def get_all_parameters(self) -> dict[str, DatabaseValueType]:
        """Return the current values of all shared parameters.

        Returns:
            Mapping of parameter IDs to their values.
        """

        return dict(ParametersRepository.get_shared_parameters())

    def get_display_groups(self) -> dict[str, dict[str, ParameterMetadata]]:
        """Return metadata grouped by display group.

        Returns:
            Mapping from display group names to parameter metadata.
        """

        return self._display_group_metadata

    async def _update_parameter_metadata_and_display_groups(
        self, parameter_metadata: ParameterMetadataDict
    ) -> None:
        """Update the cached parameter metadata and display groups.

        Compares the new metadata against the cached state. If any parameters were
        added, removed, or updated, an update event is enqueued for broadcast.

        Args:
            parameter_metadata: Dict containing both `"all parameters"` and
                `"display groups"` metadata.
        """

        logger.debug("Updating parameter metadata...")

        added_params, removed_params, updated_params = (
            get_added_removed_and_updated_keys(
                self._all_parameter_metadata, parameter_metadata["all parameters"]
            )
        )
        self._all_parameter_metadata = parameter_metadata["all parameters"]
        self._display_group_metadata = parameter_metadata["display groups"]

        # NOTE: Currently, changes in display groups alone do not trigger events.
        if added_params or removed_params or updated_params:
            emit_queue.put({"event": "parameters.update", "data": None})

    def _create_missing_influxdb_entries(self) -> None:
        """Ensure all known parameters exist in InfluxDBv1.

        For each parameter in the cached metadata, check if it exists as a field in
        InfluxDB. If not, initialize it by writing the default value via the
        `ParametersRepository`.
        """

        influxdb_param_keys = ParametersRepository.get_influxdbv1_parameter_keys()
        for parameter_id, metadata in self._all_parameter_metadata.items():
            if parameter_id not in influxdb_param_keys:
                logger.info(
                    "Creating entry %s: %s", parameter_id, metadata["default_value"]
                )
                self.update_parameter_by_id(parameter_id, metadata["default_value"])

    def initialise_parameters_repository(self) -> None:
        """Initialize the global `ParametersRepository`.

        Loads existing parameters from InfluxDB, populates the shared parameters dict in
        the shared resource manager, and marks the `ParametersRepository` as
        initialized.
        """

        icon.server.shared_resource_manager.parameters_dict.update(
            ParametersRepository.get_influxdbv1_parameters()
        )
        ParametersRepository.initialize(
            shared_parameters=icon.server.shared_resource_manager.parameters_dict
        )
        logger.info("ParametersRepository successfully initialised.")
