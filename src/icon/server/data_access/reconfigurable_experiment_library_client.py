"""Client which can be used with the configuration controller."""

import importlib
import logging
from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from typing import TYPE_CHECKING, Any

from icon.config.reloader import Reloader, ReloadError
from icon.server.data_access.experiment_library_client import (
    ExperimentLibraryClient,
    FallbackExperimentLibraryClient,
    ParameterMetadataDict,
)

if TYPE_CHECKING:
    from icon.server.api.models.experiment_dict import ExperimentDict
    from icon.server.data_access.experiment_data import (
        DatabaseValueType,
        ReadoutMetadata,
    )


logger = logging.getLogger(__name__)


def load_client(
    module: str, client_class: str, client_args: dict[str, Any]
) -> ExperimentLibraryClient:
    try:
        exp_lib_client_module = importlib.import_module(module)
        exp_lib_client_class = getattr(exp_lib_client_module, client_class)
        logger.info("Using experiment library client %s.%s", module, client_class)
        return exp_lib_client_class(**client_args)
    except (ValueError, ImportError, AttributeError, TypeError) as e:
        raise ReloadError(
            "Experiment library client is misconfigured.\n"
            f"configured module: {module}\n"
            f"configured class: {client_class}\n"
            f"Error message: {e}\n"
            "Please reconfigure!"
        ) from None


class ReconfigurableExperimentLibraryClient(ExperimentLibraryClient):
    """Wrapper reconfiguring an underlying client, whenever relevant config changes."""

    def __init__(self) -> None:
        self.client = FallbackExperimentLibraryClient()
        self.reloader = Reloader(
            load_client,
            fallback_obj=self.client,
            subconfig=lambda config: {
                key: val
                for key, val in config.experiment_library.model_dump().items()
                if key != "update_interval"
            },
        )
        self.client = self.reloader.reload()
        self._pinned = False

    def _reload(self) -> ExperimentLibraryClient:
        """Return the client of the current configuration, or the pinned client."""
        if not self._pinned:
            self.client = self.reloader.reload()
        return self.client

    def is_configured(self) -> bool:
        return self.reloader.is_configured()

    @contextmanager
    def pinned(self) -> Iterator[None]:
        """Keep the client of the current configuration for the calls in the context.

        A change of the configuration takes effect after the context, e.g. once a
        pre-processing worker has finished its job.
        """
        if self._pinned:
            yield
            return
        self._reload()
        self._pinned = True
        try:
            yield
        finally:
            self._pinned = False

    def checkout_revision(self, revision: str | None) -> str | None:
        """Restore a state of the library defined by `revision`.

        Return a string representing the state of the checked out library.

        Should be implemented by experiment library clients based on a git repository.
        """
        return self._reload().checkout_revision(revision)

    def isolated(self) -> AbstractContextManager[ExperimentLibraryClient]:
        """Create a context manager for a temporary isolated copy of the library.

        By default isolation is not implemented and only a reference to
        the original library is returned.
        """
        return self._reload().isolated()

    @contextmanager
    def reuse_venv(self) -> Iterator[None]:
        """Keep the library loaded between the calls in the context.

        The calls in the context may share state the library keeps. They are all made
        with the client keeping the library loaded, see `pinned`.
        """
        with self.pinned(), self.client.reuse_venv():
            yield

    async def load_metadata(self) -> "tuple[ExperimentDict, ParameterMetadataDict]":
        """Load the experiment and parameter metadata.

        To support hot-reloading of user data modules, this is a method
        and not static data.
        """
        return await self._reload().load_metadata()

    async def load_device_order(self) -> list[str]:
        """Return the device ids in the order the devices should be handled by the hardware processor."""
        return await self._reload().load_device_order()

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
        return await self._reload().create_hardware_instructions(
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
    ) -> "list[tuple[str, ReadoutMetadata]]":
        """Fetch metadata about the readout data an experiment will yield.

        Args:
            exp_module_name: Module name of the experiment.
            exp_instance_name: Name of the experiment instance.
            parameter_dict: Mapping of parameter IDs to values.

        Returns:
            Device ID, readout metadata pairs for the experiment.
        """
        return await self._reload().get_experiment_readout_metadata(
            exp_module_name=exp_module_name,
            exp_instance_name=exp_instance_name,
            parameter_dict=parameter_dict,
        )

    async def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        return await self._reload().get_setup_hardware_description()
