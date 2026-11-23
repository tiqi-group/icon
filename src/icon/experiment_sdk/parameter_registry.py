from collections import defaultdict
from typing import TypedDict

from pycrystal.database.database import DatabaseValueType


class ParameterMetadata(TypedDict):
    display_name: str
    unit: str
    default_value: DatabaseValueType
    min_value: float | None
    max_value: float | None
    allowed_values: list[str] | None
    read_only: bool


class ParameterRegistry:
    """A registry for managing parameters that inherit from
    `pycrystal.parameters.Parameter`.

    This class allows parameters to be registered and organized by namespaces and
    optional display groups. It provides a central location to access all registered
    parameters and supports resetting the registry to its initial state.
    """

    def __init__(self) -> None:
        self.reset()

    def add_parameters(
        self,
        parameter_dict: dict[str, ParameterMetadata],
        namespace: str,
        display_group: str | None = None,
    ) -> None:
        """Add parameters to the registry.

        Parameters:
            parameter_dict: A dictionary of parameters to add, where the keys are
                parameter IDs and the values are metadata describing the parameters.
            namespace: The namespace under which the parameters should be registered.
                This is only used if a `display_group` is provided.
            display_group: An optional display group within the namespace. If provided,
                parameters will also be organized under this display group.

        Behavior:
            - Adds parameters to the global `all_parameters` dictionary if they are not
              already registered.
            - If `display_group` is provided, organizes the parameters in the
              `namespace_registry` under the given `namespace` and `display_group`.
        """

        for parameter_id, parameter_metadata in parameter_dict.items():
            if parameter_id not in self.all_parameters:
                self.all_parameters[parameter_id] = parameter_metadata

            if display_group is not None:
                self.namespace_registry[namespace][display_group][parameter_id] = (
                    parameter_metadata
                )

    def reset(self) -> None:
        """Reset the parameter registry.

        Clears all registered parameters and reinitializes the registry structure.
        """

        self.all_parameters: dict[str, ParameterMetadata] = {}
        self.namespace_registry: dict[str, dict[str, dict[str, ParameterMetadata]]] = (
            defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(
                        lambda: {
                            "display_name": "",
                            "unit": "",
                            "default_value": 0,
                            "min_value": None,
                            "max_value": None,
                            "allowed_values": None,
                            "read_only": False,
                        }
                    )
                )
            )
        )
