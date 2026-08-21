"""Access isolated experiment libraries."""

import logging
from typing import TYPE_CHECKING, Any

from icon.server.data_access.experiment_data import ReadoutMetadata
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.venv_exec import (
    VenvWorker,
    VirtualEnvironment,
    deep_asdict,
)

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

    def reload_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Reload the experiment and parameter metadata.

        This mainly exists to support hot-reloading of user data modules.
        """
        return self.experiment_metadata, self.parameter_metadata

    def create_hardware_instructions(
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

    def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        raise NotImplementedError("Must be implemented by a subclass")

    def run_experiment_post_processing(
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
        has no post-processing rather than raising (matching the default on
        `ExperimentLibraryClient.run_experiment_post_processing`), since a
        client running inside the venv subprocess crashing that subprocess
        on an unimplemented method would be a more disruptive failure mode
        than for the other (non-venv) methods.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            result_channels: Result channel values of the processed data point.
            post_processing_output: Post-processing state returned by the
                previous call for this job (empty list on the first call).
            shot_channels: Per-shot counts of the processed data point.

        Returns:
            Dictionary with post-processing results (see
            `ExperimentLibraryClient.run_experiment_post_processing`).
        """
        return {
            "has_post_processing": False,
            "updated_parameters": {},
            "updated_result_channels": {},
            "post_processing_output": post_processing_output,
            "db_upload_interval": None,
        }


class VEnvExperimentLibraryClient(ExperimentLibraryClient):
    """Wrapper client which runs an actual client in a virtual environment."""

    def __init__(
        self,
        client: BlockingExperimentLibraryClient,
        venv_path: str,
    ) -> None:
        self.venv = VirtualEnvironment(venv_path)
        self.client = client
        self._post_processing_worker: VenvWorker | None = None

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata."""
        return await self.venv.run(self.client.reload_metadata, logger=venv_logger)

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
            serialize=deep_asdict,
            deserialize=ReadoutMetadata.from_dict,
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

    async def run_experiment_post_processing(
        self,
        *,
        exp_module_name: str,
        exp_instance_name: str,
        parameter_dict: "dict[str, DatabaseValueType]",
        result_channels: dict[str, float],
        post_processing_output: list[float],
        shot_channels: dict[str, list[int]] | None = None,
    ) -> dict[str, Any]:
        """Run an experiment's optional ``post_processing`` method.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.
            result_channels: Result channel values of the processed data point.
            post_processing_output: Post-processing state returned by the
                previous call for this job (empty list on the first call).
            shot_channels: Per-shot counts of the processed data point.

        Returns:
            Dictionary with post-processing results (see
            `ExperimentLibraryClient.run_experiment_post_processing`).
        """
        worker = await self._get_post_processing_worker()
        return await worker.run(
            self.client.run_experiment_post_processing,
            args={
                "exp_module_name": exp_module_name,
                "exp_instance_name": exp_instance_name,
                "parameter_dict": parameter_dict,
                "result_channels": result_channels,
                "post_processing_output": post_processing_output,
                "shot_channels": shot_channels,
            },
            logger=venv_logger,
        )

    async def _get_post_processing_worker(self) -> VenvWorker:
        """Start (once) and reuse the subprocess for this client's post-processing.

        Post-processing is called once per job data point, so spawning a
        subprocess per call (as `VirtualEnvironment.run` does for the other
        methods) is wasteful; instead a single subprocess is started on the
        first call and kept alive for the rest of this client's lifetime
        (i.e. for the whole job -- see `aclose`).
        """
        if self._post_processing_worker is None:
            self._post_processing_worker = await self.venv.start_worker(
                self.client.run_experiment_post_processing
            )
        return self._post_processing_worker

    async def aclose(self) -> None:
        """Stop the persistent post-processing worker, if one was started."""
        if self._post_processing_worker is not None:
            await self._post_processing_worker.stop()
            self._post_processing_worker = None
