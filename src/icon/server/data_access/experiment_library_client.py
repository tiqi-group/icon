"""Abstraction over experiment library clients."""

from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.api.models.parameter_metadata import (
        ParameterMetadata,
    )
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.repositories.experiment_data_repository import (
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

    def checkout_revision(self, revision: str | None) -> str | None:
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
        raise NotImplementedError("Must be implemented by a subclass")

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
        raise NotImplementedError("Must be implemented by a subclass")


class FallbackExperimentLibraryClient(ExperimentLibraryClient):
    """Client for an empty library."""

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        return ({}, {"all parameters": {}, "display groups": {}})

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
        return ""

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
        return {
            "readout_channel_names": [],
            "shot_channel_names": [],
            "vector_channel_names": [],
            "readout_channel_windows": [],
            "shot_channel_windows": [],
            "vector_channel_windows": [],
        }
