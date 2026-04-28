from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.repositories.experiment_data_repository import (
        ReadoutMetadata,
    )


class MockExperimentLibraryClient:
    experiment_metadata: ClassVar[dict[str, Any]] = {}
    """Dictionary mapping the unique experiment identifier to its metadata."""
    parameter_metadata: ClassVar[dict[str, Any]] = {}
    """Dictionary of parameter metadata."""

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
        return "{}"

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
        return {}
