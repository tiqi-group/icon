import logging
import tempfile
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
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.experiment_library_client import ParameterMetadataDict
    from icon.server.data_access.repositories.experiment_data_repository import (
        PlotWindowMetadata,
        ReadoutMetadata,
    )

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
    def parameter_metadata(self, value: "ParameterMetadataDict") -> None:
        raise RuntimeError("Read only attribute")

    @property
    def experiment_metadata(self) -> "ExperimentDict":
        return collect_experiment_metadata(self.experiment_library_module)

    @experiment_metadata.setter
    def experiment_metadata(self, value: "ExperimentDict") -> None:
        raise RuntimeError("Read only attribute")

    @staticmethod
    def generate_json_sequence(
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
        exp_instance = import_experiment_instance(exp_module_name, exp_instance_name)

        return exp_instance.pulse_sequence_str_from_args(
            parameter_dict,
            n_shots,
            LOG_LEVEL,
        )

    @staticmethod
    def get_experiment_readout_metadata(
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
        pycrystal.parameters.Parameter.db = pycrystal.database.local_cache.LocalCache(
            key_val_dict=parameter_dict,
        )

        exp_instance = import_experiment_instance(exp_module_name, exp_instance_name)
        readout = exp_instance.get_readout_metadata(parameter_dict, LOG_LEVEL)

        def plot_window_metadata(data: Any) -> "PlotWindowMetadata":
            return {
                "name": data.name,
                "index": data.index,
                "type": data.type.name.lower(),
                "channel_names": data.channel_names,
            }

        return {
            "readout_channel_names": readout.readout_channel_names,
            "shot_channel_names": readout.shot_channel_names,
            "vector_channel_names": readout.vector_channel_names,
            "readout_channel_windows": [
                plot_window_metadata(m) for m in readout.readout_channel_windows
            ],
            "shot_channel_windows": [
                plot_window_metadata(m) for m in readout.shot_channel_windows
            ],
            "vector_channel_windows": [
                plot_window_metadata(m) for m in readout.vector_channel_windows
            ],
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
