"""Access isolated experiment libraries."""

import logging
from typing import TYPE_CHECKING, Any

from icon.server.api.models.experiment_dict import ExperimentMetadata
from icon.server.data_access.experiment_data import (
    ExperimentDataPoint,
    ExperimentDeviceDataPoint,
    ReadoutMetadata,
    Readouts,
)
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.venv_exec import VirtualEnvironment, deep_asdict

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

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
        n_shots: int,
    ) -> dict[str, str]:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            n_shots: Number of shots.

        Returns:
            Mapping of device_ids to the instructions generated per device.
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

    def post_process(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
        data_point: ExperimentDataPoint,  # noqa: ARG002
    ) -> ExperimentDataPoint | None:
        """Run the experiment's post-processing on a data point.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Parameter values the data point's hardware instructions
                were generated with.
            data_point: The data point as read out from the devices.

        Returns:
            The processed data point, or None if the experiment defines no
            post-processing. By default experiments define none.
        """
        return None

    def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        raise NotImplementedError("Must be implemented by a subclass")


def deserialize_data_point(data: dict[str, Any] | None) -> ExperimentDataPoint | None:
    """Rebuild a data point serialized with `deep_asdict`, which has readouts."""
    if data is None:
        return None
    return ExperimentDataPoint(
        index=data["index"],
        scan_params=data["scan_params"],
        timestamp=data["timestamp"],
        device_data=[
            ExperimentDeviceDataPoint(
                device_id=device_data["device_id"],
                readouts=Readouts(**device_data["readouts"]),
                hardware_instructions=device_data["hardware_instructions"],
            )
            for device_data in data["device_data"]
        ],
    )


def serialize_metadata(
    d: "tuple[ExperimentDict, ParameterMetadataDict]",
) -> "tuple[dict[str, Any], ParameterMetadataDict]":
    """Shallow dataclass -> dict conversion as dataclasses.asdict does not seem to work here."""
    return ({key: vars(val) for key, val in d[0].items()}, d[1])


def deserialize_metadata(
    d: "tuple[dict[str, Any], ParameterMetadataDict]",
) -> "tuple[ExperimentDict, ParameterMetadataDict]":
    return ({key: ExperimentMetadata(**val) for key, val in d[0].items()}, d[1])


class VEnvExperimentLibraryClient(ExperimentLibraryClient):
    """Wrapper client which runs an actual client in a virtual environment."""

    def __init__(
        self,
        client: BlockingExperimentLibraryClient,
        venv_path: str,
    ) -> None:
        self.venv = VirtualEnvironment(venv_path)
        self.client = client

    def reuse_venv(self) -> "AbstractContextManager[None]":
        """Create a context manager running the calls in it in one process.

        See `VirtualEnvironment.reuse_venv`.
        """
        return self.venv.reuse_venv()

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata."""
        return await self.venv.run(
            self.client.reload_metadata,
            logger=venv_logger,
            serialize=serialize_metadata,
            deserialize=deserialize_metadata,
        )

    async def load_device_order(self) -> list[str]:
        """Return the device ids in the order the devices should be handled by the hardware processor."""
        return await self.venv.run(self.client.load_device_order, logger=venv_logger)

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        n_shots: int,
    ) -> dict[str, str]:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            n_shots: Number of shots.

        Returns:
            Mapping of device_ids to the instructions generated per device.
        """
        return await self.venv.run(
            self.client.create_hardware_instructions,
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

    async def post_process(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        data_point: ExperimentDataPoint,
    ) -> ExperimentDataPoint | None:
        """Run the experiment's post-processing on a data point.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Parameter values the data point's hardware instructions
                were generated with.
            data_point: The data point as read out from the devices.

        Returns:
            The processed data point, or None if the experiment defines no
            post-processing.
        """
        return await self.venv.run(
            self.client.post_process,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
                "data_point": data_point,
            },
            logger=venv_logger,
            serialize=deep_asdict,
            deserialize=deserialize_data_point,
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
