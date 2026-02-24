"""Client which can be used with the configuration controller."""

import importlib
import logging
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any

from icon.config.config import get_config
from icon.server.data_access.experiment_library_client import (
    ExperimentLibraryClient,
    FallbackExperimentLibraryClient,
    ParameterMetadataDict,
)

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.repositories.experiment_data_repository import (
        ReadoutMetadata,
    )

logger = logging.getLogger(__name__)


class ReconfigurableExperimentLibraryClient(ExperimentLibraryClient):
    """Wrapper reconfiguring an underlying client, whenever relevant config changes."""

    def __init__(self) -> None:
        self.client = FallbackExperimentLibraryClient()
        self.current_config: dict[str, Any] = {}
        self.reload()

    def reload(self) -> None:
        config = get_config().experiment_library
        new_config = config.model_dump()
        if new_config == self.current_config:
            return
        logger.info(
            "Using experiment library client %s.%s", config.module, config.client_class
        )
        self.current_config = new_config
        try:
            exp_lib_client_module = importlib.import_module(config.module)
            exp_lib_client_class = getattr(exp_lib_client_module, config.client_class)
            self.client = exp_lib_client_class(**config.client_args)
        except (ValueError, ImportError, AttributeError) as e:
            logger.warning(
                "Experiment library client is misconfigured.\n"
                "configured module: %s\n"
                "configured class: %s\n"
                "Error message: %s\n"
                "Please reconfigure!",
                config.module,
                config.client_class,
                e,
            )

    def is_configured(self) -> bool:
        self.reload()
        return not isinstance(self.client, FallbackExperimentLibraryClient)

    def checkout_revision(self, revision: str | None) -> str | None:
        """Restore a state of the library defined by `revision`.

        Return a string representing the state of the checked out library.

        Should be implemented by experiment library clients based on a git repository.
        """
        self.reload()
        return self.client.checkout_revision(revision)

    def isolated(self) -> AbstractContextManager[ExperimentLibraryClient]:
        """Create a context manager for a temporary isolated copy of the library.

        By default isolation is not implemented and only a reference to
        the original library is returned.
        """

        self.reload()
        return self.client.isolated()

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        self.reload()
        return await self.client.load_metadata()

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
        self.reload()
        return await self.client.generate_json_sequence(
            exp_module_name=exp_module_name,
            exp_instance_name=exp_instance_name,
            parameter_dict=parameter_dict,
            n_shots=n_shots,
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
        self.reload()
        return await self.client.get_experiment_readout_metadata(
            exp_module_name=exp_module_name,
            exp_instance_name=exp_instance_name,
            parameter_dict=parameter_dict,
        )
