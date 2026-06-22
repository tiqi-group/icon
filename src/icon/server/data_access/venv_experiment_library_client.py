"""Access isolated experiment libraries."""

import logging
from typing import TYPE_CHECKING, Any

from icon.server.data_access.experiment_data import ReadoutMetadata
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.venv_exec import VirtualEnvironment, deep_asdict

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import ExperimentDict
    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.data_access.experiment_library_client import ParameterMetadataDict

venv_logger = logging.getLogger("venv")


class BlockingExperimentLibraryClient:
    """Blocking version of the async `ExperimentLibraryClient`."""

    experiment_metadata: "ExperimentDict"
    """Dictionary mapping the unique experiment identifier to its metadata."""
    parameter_metadata: "ParameterMetadataDict"
    """Dictionary of parameter metadata."""
    device_order: list[str]
    """List of devices ids in the order the devices should be handled by the hardware processor."""

    def reload_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Reload the experiment and parameter metadata.

        This mainly exists to support hot-reloading of user data modules.
        """
        return self.experiment_metadata, self.parameter_metadata

    def load_device_order(self) -> list[str]:
        """Return the device ids in the order the devices should be handled by the hardware processor."""
        return self.device_order

    def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        device_id: str,
        n_shots: int,
    ) -> bytes:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            device_id: Id of the hardware for which to create the instructions
            n_shots: Number of shots.

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
    ) -> "list[tuple[str, ReadoutMetadata]]":
        """Fetch metadata about the readout data an experiment will yield.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Device ID, readout metadata pairs for the experiment.
        """
        raise NotImplementedError("Must be implemented by a subclass")

    def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
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

    async def load_device_order(self) -> list[str]:
        """Return the device ids in the order the devices should be handled by the hardware processor."""
        return await self.venv.run(self.client.load_device_order, logger=venv_logger)

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        device_id: str,
        n_shots: int,
    ) -> bytes:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            device_id: Id of the hardware for which to create the instructions.
            n_shots: Number of shots.

        Returns:
            JSON string containing the generated sequence.
        """
        return await self.venv.run(
            self.client.create_hardware_instructions,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
                "device_id": device_id,
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
    ) -> "list[tuple[str, ReadoutMetadata]]":
        """Fetch metadata about the readout data an experiment will yield.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Device ID, readout metadata pairs for the experiment.
        """
        return await self.venv.run(
            self.client.get_experiment_readout_metadata,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
            },
            logger=venv_logger,
            serialize=deep_asdict,
            deserialize=lambda meta: [
                (dev_id, ReadoutMetadata.from_dict(dev)) for (dev_id, dev) in meta
            ],
        )

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        return await self.venv.run(
            self.client.get_setup_hardware_description,
            args={},
            logger=venv_logger,
        )
