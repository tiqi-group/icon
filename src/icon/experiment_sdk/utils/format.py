import textwrap
from typing import Any


def format_parameter(namespace: str, parameter_group: str, **kwargs: Any) -> str:
    text = f"\nNamespace: {namespace}\nParameter group: {parameter_group}\n"
    for key, value in kwargs.items():
        text += f"{key}: {value}\n"
    return textwrap.indent(text, "     ")
