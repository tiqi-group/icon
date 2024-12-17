from __future__ import annotations

import logging
import sys
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict

from typing_extensions import NotRequired

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

if TYPE_CHECKING:
    from icon.client.client import Client
    from icon.server.data_access.repositories.experiment_metadata_repository import (
        ExperimentMetadata,
    )
    from icon.server.data_access.repositories.parameter_metadata_repository import (
        ParameterMetadata,
    )

logger = logging.getLogger(__name__)


class ScanParameter(TypedDict):
    parameter: ParameterProxy | str
    """A ParameterProxy object retrieved from the API, or the parameter identifier. """
    values: dict[str, Any] | list[Any]
    """ Either a dictionary with 'start', 'stop', and 'num_points' keys or a list of
    explicit values. """
    randomized: NotRequired[bool]
    """Boolean indicating whether the values should be shuffled."""
    reversed: NotRequired[bool]
    """Boolean indicating whether the values should be reversed."""


def get_experiment_identifier_dict(experiments: list[str]) -> dict[str, str]:
    """
    Processes a list of experiment strings to create a dictionary of unique identifiers.

    The keys are unique identifiers:
    - If the instance name (within brackets) is unique, it is used as the key.
    - If not, the instance name is appended with the class name to make it unique.

    The values are the original full names from the input list.

    Args:
        experiments:
            List of experiment strings in the format 'path.to.ClassName (InstanceName)'.

    Returns:
        A dictionary where keys are unique identifiers and values are the full names.
    """
    # Extract instance names and track their counts
    instance_names = [entry.split("(")[-1].strip(")") for entry in experiments]
    instance_counts = Counter(instance_names)

    # Create the result dictionary
    identifier_dict = {}

    for entry in experiments:
        full_name, instance_name = entry.rsplit("(", 1)
        instance_name = instance_name.strip(")")
        class_name = full_name.split(".")[-1].strip()

        # Determine unique identifier
        if instance_counts[instance_name] == 1:
            unique_identifier = instance_name
        else:
            unique_identifier = f"{instance_name} ({class_name})"

        # Add to the dictionary
        identifier_dict[unique_identifier] = entry

    return identifier_dict


def get_parameter_identifier_mapping(
    display_group_metadata: dict[str, ParameterMetadata],
) -> dict[str, str]:
    parameter_id_mapping: dict[str, str] = {}
    for parameter_id, parameter_metadata in display_group_metadata.items():
        parameter_id_mapping[parameter_metadata["display_name"]] = parameter_id
    return parameter_id_mapping


class ParameterProxy:
    def __init__(
        self, client: Client, parameter_id: str, parameter_metadata: ParameterMetadata
    ) -> None:
        self._client = client
        self._parameter_metadata = parameter_metadata
        self._parameter_id = parameter_id

    @property
    def value(self) -> Any:
        return self._client.trigger_method(
            "parameters.get_parameter_by_id",
            kwargs={
                "parameter_id": self._parameter_id,
            },
        )

    @value.setter
    def value(self, value: Any) -> None:
        self._client.trigger_method(
            "parameters.update_parameter_by_id",
            kwargs={
                "parameter_id": self._parameter_id,
                "value": value,
            },
        )

    def __repr__(self) -> str:
        return (
            f"<Parameter: {self._parameter_metadata['display_name']}>\n"
            f"    id={self._parameter_id}\n"
            f"    default={self._parameter_metadata['default_value']}\n"
            f"    min={self._parameter_metadata['min_value']}\n"
            f"    max={self._parameter_metadata['max_value']}\n"
        )


class DisplayGroupProxy:
    def __init__(
        self,
        client: Client,
        display_group_name: str,
        display_group_metadata: dict[str, ParameterMetadata],
    ) -> None:
        self._client = client
        self._display_group_metadata = display_group_metadata
        self._display_group_name = display_group_name
        self._parameter_id_mapping = get_parameter_identifier_mapping(
            self._display_group_metadata
        )

    def __getitem__(self, parameter_name: str) -> Any:
        parameter_id = self._parameter_id_mapping[parameter_name]

        return ParameterProxy(
            self._client, parameter_id, self._display_group_metadata[parameter_id]
        )

    def __setitem__(self, parameter_name: str, value: Any) -> Any:
        parameter_id = self._parameter_id_mapping[parameter_name]

        return self._client.trigger_method(
            "parameters.update_parameter_by_id",
            kwargs={
                "parameter_id": parameter_id,
                "value": value,
            },
        )

    def __repr__(self) -> str:
        repr = f"<{self._display_group_name}>"

        for parameter_id in self._display_group_metadata:
            repr += (
                f"\n    - {self._display_group_metadata[parameter_id]['display_name']}"
            )
        return repr


class ExperimentJobProxy:
    def __init__(self, *, client: Client, job_id: int) -> None:
        self._client = client
        self._job_id = job_id
        self._getting_data = False


class ExperimentProxy:
    def __init__(
        self,
        client: Client,
        experiment_id: str,
        experiment_metadata: ExperimentMetadata,
    ) -> None:
        self._client = client
        self._experiment_id = experiment_id
        self._experiment_metadata = experiment_metadata

    def __repr__(self) -> str:
        repr = (
            f"<{self._experiment_metadata['constructor_kwargs']['name']}> (Experiment: "
            f"{self._experiment_metadata['class_name']})\n"
            f"  Display Groups:"
        )
        for display_group in self._experiment_metadata["parameters"]:
            repr += f"\n    - {display_group}"

        return repr

    def __getitem__(self, display_group_name: str) -> Any:
        return DisplayGroupProxy(
            self._client,
            display_group_name,
            self._experiment_metadata["parameters"][display_group_name],
        )

    def schedule(
        self,
        scan_parameters: list[ScanParameter],
        priority: int = 20,
        repetitions: int = 1,
        local_parameters_timestamp: datetime = datetime.now(),
        git_commit_hash: str | None = None,
    ) -> ExperimentJobProxy:
        """
        Schedule an experiment scan.

        Args:
            scan_parameters:
                A list of dictionaries where each dictionary defines a scan parameter
                and its values. Each dictionary should include:
                    - 'parameter': A ParameterProxy object retrieved from the API.
                    - 'values': Either a dictionary with 'start', 'stop', and
                        'num_points' keys or a list of explicit values.
                    - 'randomized': (Optional) Boolean indicating whether the values
                        should be shuffled. Defaults to False.
                    - 'reversed': (Optional) Boolean indicating whether the values
                        should be reversed. Defaults to False.
            priority:
                Priority level of the experiment (default: 20).
            repetitions:
                Number of repetitions for the experiment to average over (default: 1).
            local_parameters_timestamp:
                Timestamp of the local parameters to be used. Defaults to the current
                time.
            git_commit_hash:
                Git commit hash of the experiment library. If None is provided, it will
                take the latest commit on the main/master branch. Defaults to None.

        Returns:
            ExperimentJobProxy: Proxy object for the scheduled experiment job.
        """

        for parameter in scan_parameters:
            if isinstance(parameter["parameter"], ParameterProxy):
                parameter["parameter"] = parameter["parameter"]._parameter_id

        job_id: int = self._client.trigger_method(
            "scheduler.submit_job",
            kwargs={
                "experiment_id": self._experiment_id,
                "scan_parameters": scan_parameters,
                "priority": priority,
                "local_parameters_timestamp": local_parameters_timestamp,
                "repetitions": repetitions,
                "git_commit_hash": git_commit_hash,
            },
        )
        return ExperimentJobProxy(client=self._client, job_id=job_id)


class ExperimentsController:
    def __init__(self, client: Client) -> None:
        self._client = client
        self.__update_experiments()

    def __update_experiments(self) -> None:
        self._experiments = self._client.trigger_method("experiments.get_experiments")
        self._experiments_id_mapping = get_experiment_identifier_dict(self._experiments)

    def __repr__(self) -> str:
        repr = "<Experiments>\n"
        for experiment in sorted(self._experiments_id_mapping):
            repr += f"  - {experiment}\n"
        return repr

    def __getitem__(self, key: str) -> ExperimentProxy | None:
        experiment_id = self._experiments_id_mapping.get(key, None)
        if experiment_id:
            return ExperimentProxy(
                self._client, experiment_id, self._experiments[experiment_id]
            )

        return None
