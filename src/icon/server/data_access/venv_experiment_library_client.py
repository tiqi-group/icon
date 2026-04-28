"""Access isolated experiment libraries."""

import logging
from typing import TYPE_CHECKING

from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.venv_exec import VirtualEnvironment

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import ExperimentDict
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.experiment_library_client import ParameterMetadataDict
    from icon.server.data_access.repositories.experiment_data_repository import (
        ReadoutMetadata,
    )

venv_logger = logging.getLogger("venv")


class BlockingExperimentLibraryClient:
    """Blocking version of the async `ExperimentLibraryClient`."""

    experiment_metadata: "ExperimentDict"
    """Dictionary mapping the unique experiment identifier to its metadata."""
    parameter_metadata: "ParameterMetadataDict"
    """Dictionary of parameter metadata."""

    def reload_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Reload the experiment and parameter metadata.

        This mainly exists to support hot-reloading of user data modules.
        """
        return self.experiment_metadata, self.parameter_metadata

    def generate_json_sequence(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        n_shots: int,
    ) -> str:
        """Generate a JSON sequence for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            JSON string containing the generated sequence.
        """
        raise NotImplementedError("Must be implemented by a subclass")

    def get_experiment_readout_metadata(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
    ) -> "ReadoutMetadata":
        """Fetch readout metadata for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Dictionary containing readout metadata for the experiment.
        """
        raise NotImplementedError("Must be implemented by a subclass")


class VEnvExperimentLibraryClient(ExperimentLibraryClient):
    """Wrapper client which runs an actual client in a virtual environment."""

    def __init__(
        self,
        client: BlockingExperimentLibraryClient,
        venv_path: str,
    ) -> None:
        self.venv = VirtualEnvironment(venv_path)
        self.client = client

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata."""
        return await self.venv.run(self.client.reload_metadata, logger=venv_logger)

    async def generate_json_sequence(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        n_shots: int,
    ) -> str:
        """Generate a JSON sequence for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            JSON string containing the generated sequence.
        """
        return await self.venv.run(
            self.client.generate_json_sequence,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
                "n_shots": n_shots,
            },
            logger=venv_logger,
        )

    async def get_experiment_readout_metadata(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
    ) -> "ReadoutMetadata":
        """Fetch readout metadata for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Dictionary containing readout metadata for the experiment.
        """
        return await self.venv.run(
            self.client.get_experiment_readout_metadata,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
            },
            logger=venv_logger,
        )
