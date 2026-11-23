from __future__ import annotations

from enum import Enum

from pycrystal.utils import ParameterTypes


def get_parameter_identifier_from_specifiers(
    namespace: str,
    parameter_group: str,
    param_type: ParameterTypes,
    **kwargs: Enum | str,
) -> str:
    param_parts = [
        f"{key}='{value.__class__.__name__}.{value.name}'"
        if isinstance(value, Enum)
        else f"{key}='{value}'"
        for key, value in sorted(kwargs.items())
    ]

    return (
        f"namespace={namespace!r} parameter_group={parameter_group!r} "
        f"param_type={str(param_type)!r} " + " ".join(param_parts)
    ).strip()


def get_specifiers_from_parameter_identifier(
    parameter_identifier: str,
) -> tuple[str, str, ParameterTypes, dict[str, str], dict[str, str]]:
    import re

    # Regex pattern to match key='value' pairs, including namespace and parameter_group
    pattern = re.compile(r"(\w+)='([^']*)'")
    matches = pattern.findall(parameter_identifier)

    # Construct the dictionary from the matched key-value pairs
    all_specifiers = dict(matches)
    specifiers = dict(matches)

    # Pop namespace and parameter_group
    namespace = specifiers.pop("namespace")
    parameter_group = specifiers.pop("parameter_group")
    param_type = ParameterTypes[specifiers.pop("param_type").split(".")[1]]

    return namespace, parameter_group, param_type, specifiers, all_specifiers
