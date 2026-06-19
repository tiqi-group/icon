"""Abstraction over experiment library clients."""

from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, Any, TypedDict

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.api.models.parameter_metadata import (
        ParameterMetadata,
    )
    from icon.server.data_access.experiment_data import (
        DatabaseValueType,
        ReadoutMetadata,
    )

ParameterMetadataDict = TypedDict(
    "ParameterMetadataDict",
    {
        "all parameters": "dict[str, ParameterMetadata]",
        "display groups": "dict[str, dict[str, ParameterMetadata]]",
    },
)
"""Dictionary of parameter metadata."""


class ExperimentLibraryClient:
    """Abstract experiment library client."""

    def checkout_revision(self, revision: str | None) -> str | None:  # noqa: ARG002
        """Restore a state of the library defined by `revision`.

        Return a string representing the state of the checked out library.

        Should be implemented by experiment library clients based on a git repository.
        """
        return None

    def isolated(self) -> "AbstractContextManager[ExperimentLibraryClient]":
        """Create a context manager for a temporary isolated copy of the library.

        By default isolation is not implemented and only a reference to
        the original library is returned.
        """
        return nullcontext(self)

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        raise NotImplementedError("Must be implemented by a subclass")

    async def load_device_order(self) -> list[str]:
        """Return an ordered list of device ids.

        Devices should be triggered in that order by the hardware processor.
        """
        raise NotImplementedError("Must be implemented by a subclass")

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
            n_shots: Number of shots

        Returns:
            JSON string containing the generated sequence.
        """
        raise NotImplementedError("Must be implemented by a subclass")

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
        raise NotImplementedError("Must be implemented by a subclass")

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup
        """
        raise NotImplementedError("Must be implemented by a subclass")


class FallbackExperimentLibraryClient(ExperimentLibraryClient):
    """Client for an empty library."""

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        return ({}, {"all parameters": {}, "display groups": {}})

    async def load_device_order(self) -> list[str]:
        """Return the device ids in the order the devices should be handled by the hardware processor."""
        return []

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
        device_id: str,  # noqa: ARG002
        n_shots: int,  # noqa: ARG002
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
        return b""

    async def get_experiment_readout_metadata(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
    ) -> "list[tuple[str, ReadoutMetadata]]":
        """Fetch metadata about the readout data an experiment will yield.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Dictionary containing readout metadata for the experiment.
        """
        return []

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        return {
            "RFs": {},
            "TTLs": {},
            "PMTs": {},
            "RTDs": {},
            "Readouts": {},
        }
