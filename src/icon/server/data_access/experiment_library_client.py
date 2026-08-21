"""Abstraction over experiment library clients."""

from contextlib import AbstractContextManager, nullcontext
from typing import TYPE_CHECKING, Any, TypedDict

from icon.server.data_access.experiment_data import ReadoutMetadata

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.api.models.parameter_metadata import (
        ParameterMetadata,
    )
    from icon.server.data_access.experiment_data import DatabaseValueType

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

    async def aclose(self) -> None:
        """Release any resources held for the job this client was used for.

        Called once a job ends. By default there is nothing to release.
        """

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        raise NotImplementedError("Must be implemented by a subclass")

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        n_shots: int,
    ) -> str:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
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

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup
        """
        raise NotImplementedError("Must be implemented by a subclass")

    async def run_experiment_post_processing(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
        result_channels: dict[str, float],  # noqa: ARG002
        post_processing_output: list[float],
        shot_channels: dict[str, list[int]] | None = None,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Run an experiment's optional ``post_processing`` method.

        By default -- i.e. for clients that predate this method, or that
        don't support post-processing -- this reports that the experiment
        has no post-processing rather than raising, since post-processing is
        an optional feature of an experiment library client.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            result_channels: Result channel values of the processed data point.
            post_processing_output: Post-processing state returned by the
                previous call for this job (empty list on the first call).
            shot_channels: Per-shot counts of the processed data point.

        Returns:
            Dictionary with keys:
            - "has_post_processing": whether the experiment defines the method.
            - "updated_parameters": parameter IDs/values changed by the method.
            - "updated_result_channels": result channels added or modified by
              the method.
            - "post_processing_output": state to pass into the next call.
            - "db_upload_interval": database upload interval in seconds, or
              None if the experiment does not define the parameter.
            - "terminate": whether the experiment's ``termination_condition``
              requested the job to be stopped.
        """
        return {
            "has_post_processing": False,
            "updated_parameters": {},
            "updated_result_channels": {},
            "post_processing_output": post_processing_output,
            "db_upload_interval": None,
            "terminate": False,
        }


class FallbackExperimentLibraryClient(ExperimentLibraryClient):
    """Client for an empty library."""

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        return ({}, {"all parameters": {}, "display groups": {}})

    async def create_hardware_instructions(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
        n_shots: int,  # noqa: ARG002
    ) -> str:
        """Generate hardware instructions for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            n_shots: Number of shots.

        Returns:
            JSON string containing the generated sequence.
        """
        return ""

    async def get_experiment_readout_metadata(
        self,
        *,
        exp_module_name: str,  # noqa: ARG002
        exp_instance_name: str,  # noqa: ARG002
        parameter_dict: "dict[str, DatabaseValueType]",  # noqa: ARG002
    ) -> "ReadoutMetadata":
        """Fetch readout metadata for an experiment.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Dictionary containing readout metadata for the experiment.
        """
        return ReadoutMetadata(
            readout_channel_names=[],
            shot_channel_names=[],
            vector_channel_names=[],
            readout_channel_windows=[],
            shot_channel_windows=[],
            vector_channel_windows=[],
        )

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
