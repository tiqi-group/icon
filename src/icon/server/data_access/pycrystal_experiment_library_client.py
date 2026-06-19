import importlib
import logging
import tempfile
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pycrystal.database.local_cache
import pycrystal.parameters
from pycrystal.parameters import Parameter
from pycrystal.utils.helpers import (
    collect_experiment_metadata,
    import_experiment_instance,
)

import icon.server.utils.git_helpers
from icon.server.data_access.experiment_data import (
    PlotWindowMetadata,
    ReadoutMetadata,
)
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.venv_experiment_library_client import (
    BlockingExperimentLibraryClient,
    VEnvExperimentLibraryClient,
)

if TYPE_CHECKING:
    from typing import Self

    from icon.server.api.models.experiment_dict import (
        ExperimentDict,
    )
    from icon.server.data_access.experiment_data import DatabaseValueType
    from icon.server.data_access.experiment_library_client import ParameterMetadataDict

logger = logging.getLogger("experiment_library")
logging.getLogger("pycrystal").setLevel(logging.ERROR)
logging.getLogger("ionpulse_sequence_generator").setLevel(logging.ERROR)
LOG_LEVEL = logging.INFO


class AsyncPyCrystalClient(VEnvExperimentLibraryClient):
    def __init__(
        self,
        checkout_path: str,
        repo: str,
        experiment_library_module: str = "experiment_library",
    ) -> None:
        super().__init__(
            client=PyCrystalClient(experiment_library_module),
            venv_path=str(Path(checkout_path) / ".venv"),
        )
        self.repo = GitRepo(repo_url=repo, local_path=checkout_path).clone()
        self.experiment_library_module = experiment_library_module

    def checkout_revision(self, revision: str | None) -> str | None:
        self.repo.checkout(revision)
        return self.repo.local_path

    @contextmanager
    def isolated(self) -> Iterator[ExperimentLibraryClient]:
        with tempfile.TemporaryDirectory() as tmp_dir:
            yield type(self)(
                checkout_path=tmp_dir,
                repo=self.repo.repo_url,
                experiment_library_module=self.experiment_library_module,
            )


class PyCrystalClient(BlockingExperimentLibraryClient):
    def __init__(self, experiment_library_module: str) -> None:
        self.experiment_library_module = experiment_library_module

    @property
    def device_order(self) -> list[str]:
        # TODO(g-braeunlich): https://github.com/tiqi-group/icon/issues/110
        raise NotImplementedError("Not yet available in pycrystal")

    @device_order.setter
    def device_order(self, value: list[str]) -> None:  # noqa: ARG002
        raise RuntimeError("Read only attribute")

    @property
    def parameter_metadata(self) -> "ParameterMetadataDict":
        parameter_registry = Parameter.registry.namespace_registry
        return {
            "all parameters": Parameter.registry.all_parameters,
            "display groups": {
                f"{namespace} ({display_group})": parameter_dict
                for namespace, display_groups in parameter_registry.items()
                for display_group, parameter_dict in display_groups.items()
            },
        }

    @parameter_metadata.setter
    def parameter_metadata(self, value: "ParameterMetadataDict") -> None:  # noqa: ARG002
        raise RuntimeError("Read only attribute")

    @property
    def experiment_metadata(self) -> "ExperimentDict":
        return collect_experiment_metadata(self.experiment_library_module)

    @experiment_metadata.setter
    def experiment_metadata(self, value: "ExperimentDict") -> None:  # noqa: ARG002
        raise RuntimeError("Read only attribute")

    @staticmethod
    def create_hardware_instructions(
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
            device_id: Id of the device for which to create the instructions
            n_shots: Number of shots.

        Returns:
            JSON string containing the generated sequence.
        """
        exp_instance = import_experiment_instance(exp_module_name, exp_instance_name)

        try:
            return exp_instance.pulse_sequence_from_args(
                parameter_dict,
                n_shots,
                LOG_LEVEL,
                device_id=device_id,
            )
        except AttributeError:
            warnings.warn(
                "Experiment does not define `pulse_sequence_from_args` falling back to legacy behaviour",
                category=DeprecationWarning,
                stacklevel=0,
            )
            return exp_instance.pulse_sequence_str_from_args(
                parameter_dict,
                n_shots,
                LOG_LEVEL,
            )

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
        pycrystal.parameters.Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )

        exp_instance = import_experiment_instance(exp_module_name, exp_instance_name)
        readout_per_device = exp_instance.get_readout_metadata(
            parameter_dict, LOG_LEVEL
        )
        if not isinstance(readout_per_device, list):
            warnings.warn(
                "Experiment library: `get_experiment_readout_metadata()` only returns readout metadata for a single device. It should return a list of (device id, metadata) tuples.",
                category=DeprecationWarning,
                stacklevel=0,
            )
            readout_per_device = [("zedboard", readout_per_device)]

        def plot_window_metadata(data: Any) -> "PlotWindowMetadata":
            return PlotWindowMetadata(
                name=data.name,
                index=data.index,
                type=data.type.name.lower(),
                channel_names=data.channel_names,
            )

        return [
            (
                device_id,
                ReadoutMetadata(
                    readout_channel_names=readout.readout_channel_names,
                    shot_channel_names=readout.shot_channel_names,
                    vector_channel_names=readout.vector_channel_names,
                    readout_channel_windows=[
                        plot_window_metadata(m) for m in readout.readout_channel_windows
                    ],
                    shot_channel_windows=[
                        plot_window_metadata(m) for m in readout.shot_channel_windows
                    ],
                    vector_channel_windows=[
                        plot_window_metadata(m) for m in readout.vector_channel_windows
                    ],
                ),
            )
            for device_id, readout in readout_per_device
        ]

    def get_setup_hardware_description(self) -> dict[str, dict[str, Any]]:
        """Fetch hardware description from experiment library.

        Returns:
            Dictionary containing a description of the experiment setup.
        """
        hardware = importlib.import_module(
            self.experiment_library_module + ".hardware_description.hardware"
        )

        return {
            "RFs": hardware.hardware.rf_mapping,
            "TTLs": hardware.hardware.ttl_mapping,
            "PMTs": hardware.hardware.pmt_mapping,
            "RTDs": hardware.hardware.triggered_devices_mapping,
            "Readouts": hardware.hardware.readout_mapping,
        }


class GitRepo:
    def __init__(self, local_path: str, repo_url: str) -> None:
        self.local_path = local_path
        self.repo_url = repo_url

    def clone(self) -> "Self":
        dest = self.local_path

        if not icon.server.utils.git_helpers.local_repo_exists(
            repository_dir=dest, repository=self.repo_url
        ):
            logger.info("Cloning %s -> %s", self.repo_url, dest)
            icon.server.utils.git_helpers.git_clone(repository=self.repo_url, dir=dest)
        return self

    def checkout(self, git_commit_hash: str | None) -> "Self":
        self.clone()
        if git_commit_hash is not None:
            icon.server.utils.git_helpers.checkout_commit(
                git_hash=git_commit_hash, cwd=self.local_path
            )
        return self
