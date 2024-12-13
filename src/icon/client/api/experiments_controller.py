from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from icon.client.client import Client


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


class ExperimentsController:
    def __init__(self, client: Client) -> None:
        self._client = client
        self.__update_experiments()
        print(self)

    def __update_experiments(self) -> None:
        self._experiments = self._client.trigger_method("experiments.get_experiments")
        self._experiments_id_mapping = get_experiment_identifier_dict(self._experiments)

    def __repr__(self) -> str:
        repr = "<Experiments>\n"
        for experiment in sorted(self._experiments_id_mapping):
            repr += f"  - {experiment}\n"
        return repr
