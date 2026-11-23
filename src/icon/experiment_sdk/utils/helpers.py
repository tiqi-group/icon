from __future__ import annotations

import importlib
import pkgutil
import sys
from typing import TYPE_CHECKING, Any, TypedDict

from pycrystal.device_parameters import DeviceParameters

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pycrystal.experiment import Experiment, ExperimentConfigDict
    from pycrystal.parameters import ParameterMetadata


def find_caller_module() -> tuple[str, int]:
    """Identify the first module in the call stack that does not belong to the
    `pycrystal` package and return its name along with the corresponding stack frame
    depth.

    This function iterates through the call stack, starting from the current frame, to
    find a module whose name does not start with "pycrystal.". This is useful for
    filtering out internal `pycrystal` frames, such as those related to parameter
    classes inheriting from `Parameter`.

    Returns:
        A tuple containing:
            - The name of the first module in the stack that is not part of `pycrystal`.
            - The depth of the corresponding stack frame.
    """

    frame_depth = 0
    module_name = "pycrystal.parameters"
    # need to loop until the module name does not start with "pycrystal." to account for
    # parameter classes inheriting from Parameter
    while module_name.startswith("pycrystal."):
        frame_depth += 1
        frame = sys._getframe(frame_depth)
        module_name = frame.f_globals["__name__"]

    return module_name, frame_depth


def get_config_from_module_name(
    module_name: str,
) -> ExperimentConfigDict:
    """Retrieve the `CONFIGURATION` dictionary from the specified module and merge it
    with a default configuration. The configuration from the module takes precedence
    over the default configuration.

    Args:
        module_name: The name of the module from which to retrieve the `CONFIGURATION`
            variable.

    Returns:
        A dictionary containing the merged configuration, where the module's
        `CONFIGURATION` overrides the default values.
    """
    experiment_module = importlib.import_module(module_name)

    default_config: ExperimentConfigDict = {
        "experiment_instances": [],
        "display_groups": set(),
        "display_group_modules": {
            module_name,
        },
    }

    return default_config | getattr(experiment_module, "CONFIGURATION", default_config)


def import_experiment_instance(module_name: str, experiment_name: str) -> Experiment:
    """Import an experiment instance from a module.

    Args:
        module_name: The name of the module from which to import.
        member: The name of the experiment type to instanciate.

    Returns:
        The impored experiment instance.

    """
    config = get_config_from_module_name(module_name)
    exp_class, exp_kwargs = next(
        (exp_class, exp_kwargs)
        for exp_class, exp_kwargs in config["experiment_instances"]
        if exp_kwargs["name"] == experiment_name
    )
    return exp_class(**exp_kwargs)


def get_experiment_instance_display_groups(
    module_name: str, experiment_instance_name: str
) -> dict[str, dict[str, ParameterMetadata]]:
    """Retrieve the display groups for a specific experiment instance.

    This method combines the display groups defined in the module's configuration
    with the parameters defined within the specified experiment class instance.

    Args:
        module_name: The name of the module where the experiment is defined.
        experiment_instance_name: The name of the experiment instance for which to
            retrieve display groups.

    Returns:
        A dictionary where each key is a display group name, and the corresponding value
        is another dictionary containing parameter metadata for that group.
    """

    from pycrystal.parameters import Parameter

    display_group_dict = get_display_group_list_from_module_name(module_name)

    config = get_config_from_module_name(module_name)

    for experiment, kwargs in config["experiment_instances"]:
        if kwargs["name"] != experiment_instance_name:
            continue

        experiment(**kwargs)
        experiment_instance_module_name = (
            f"{module_name}.{experiment.__name__}.{experiment_instance_name}"
        )
        parameter_groups = Parameter.registry.namespace_registry[
            experiment_instance_module_name
        ]
        display_group_dict.update(parameter_groups)

    return display_group_dict


def get_display_group_list_from_module_name(
    module_name: str,
) -> dict[str, dict[str, ParameterMetadata]]:
    """Retrieve the display groups defined in the specified module's configuration.

    This method processes the `display_groups` and `display_group_modules` keys from
    the module's configuration to construct a dictionary of display groups and their
    associated parameters.

    Args:
        module_name: The name of the module from which to retrieve the display groups.

    Returns:
        A dictionary where each key is a display group name, and the corresponding value
        is another dictionary containing parameter metadata for that group.
    """

    from pycrystal.parameters import Parameter

    display_group_dict: dict[str, dict[str, ParameterMetadata]] = {}

    # 1. Get CONFIGURATION from class module
    # 2. For each display group (that is not an instance of DeviceParameters), get the
    #    parameters from the Parameter registry and add the display group to the
    #    LibraryExperiment
    # 3. For each display group in the display_group_modules, add it to the
    #    LibraryExperiment

    config = get_config_from_module_name(module_name)

    for display_group in config["display_groups"]:
        if isinstance(display_group, DeviceParameters):
            continue

        try:
            display_group_name = display_group.display_name()
        except Exception:
            display_group_name = display_group.__name__

        parameters = Parameter.registry.namespace_registry[display_group.__module__][
            display_group_name
        ]
        group_to_add: dict[str, ParameterMetadata] = {}
        group_to_add.update(dict(parameters.items()))

        display_group_dict[display_group_name] = group_to_add

    for display_group_module in config["display_group_modules"]:
        for display_group_name, parameters in Parameter.registry.namespace_registry[
            display_group_module
        ].items():
            group_to_add = {}
            for parameter_identifier, parameter_metadata in parameters.items():
                group_to_add[parameter_identifier] = parameter_metadata

            display_group_dict[display_group_name] = group_to_add

    return display_group_dict


def get_device_parameter_groups_from_module_config(
    *, config: ExperimentConfigDict
) -> list[str]:
    """Retrieves the device parameter display groups defined in the module configuration
    passed as an argument."""

    return [
        display_group.device_name
        for display_group in config["display_groups"]
        if isinstance(display_group, DeviceParameters)
    ]


class ExperimentMetadata(TypedDict):
    class_name: str
    """Name of the experiment class"""
    constructor_kwargs: dict[str, Any]
    """Arguments passed to the class constructor"""
    parameters: dict[str, dict[str, ParameterMetadata]]
    """Dictionary containing the parameter metadata for each parameter grouped by the
    display groups (i.e. the first key is the namespace of the display group followed by
    the display group name, the second key is the parameter identifier)."""
    device_parameter_groups: list[str]
    """List containing the names of the ICON device that should be shown in the
    experiment instance page."""


ExperimentDict = dict[str, ExperimentMetadata]


def collect_experiment_metadata(experiment_module: str) -> ExperimentDict:
    """Recursively collect experiment metadata (class name, constructor kwargs,
    parameters) in `experiment_module` and its submodules
    (see `get_experiment_metadata`).

    Args:
        experiment_module: Name of the experiment library module (in dot notation).

    Returns:
        Dictionary with experiment metadata mapped to experiment identifiers.


    Examples:
        ```python
        >>> list_experiment_metadata(experiment_module="experiment_library.experiments")
        ```
    """

    def walk_module(module: str) -> Iterable[str]:
        """Similar to `pkgutils.walk_modules`, but also imports modules."""
        pending_modules = [module]

        while pending_modules:
            next_module = pending_modules.pop()
            yield next_module
            try:
                path = importlib.import_module(next_module).__path__
            except AttributeError:
                continue
            new_modules = [
                next_module + "." + mod_info.name
                for mod_info in pkgutil.iter_modules(path)
            ]
            pending_modules += new_modules

    metadata_per_experiment = (
        get_experiment_metadata(experiment_module=mod_name)
        for mod_name in walk_module(experiment_module)
    )
    return {
        key: val
        for metadata in metadata_per_experiment
        for key, val in metadata.items()
    }


def get_experiment_metadata(*, experiment_module: str) -> ExperimentDict:
    """Extracts experiment metadata (class name, constructor kwargs, parameters) for
    each experiment instance defined in the `experiment_module`'s CONFIGURATION.

    Args:
        experiment_module: Name of the experiment module (in dot notation).

    Returns:
        Dictionary with experiment metadata mapped to experiment identifiers.


    Examples:
        ```python
        >>> experiment_module = "experiment_library.experiments.test_experiment"
        >>> get_experiment_metadata(experiment_module=experiment_module)
        ```
    """

    experiments: ExperimentDict = {}

    config = get_config_from_module_name(experiment_module)
    for experiment, experiment_instance_kwargs in config["experiment_instances"]:
        experiment_instance_name = experiment_instance_kwargs["name"]
        experiment_identifier = (
            f"{experiment_module}.{experiment.__name__} ({experiment_instance_name})"
        )
        experiments[experiment_identifier] = {
            "class_name": experiment.__name__,
            "constructor_kwargs": experiment_instance_kwargs,
            "parameters": get_experiment_instance_display_groups(
                experiment_module, experiment_instance_name
            ),
            "device_parameter_groups": get_device_parameter_groups_from_module_config(
                config=config
            ),
        }

    return experiments
