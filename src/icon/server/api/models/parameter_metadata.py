from typing import Any
import sys
if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


class ParameterMetadata(TypedDict):
    """Metadata describing a single parameter."""

    display_name: str
    """Human-readable name of the parameter."""
    unit: str
    """Unit in which the parameter value is expressed."""
    default_value: float | int
    """Default value assigned to the parameter."""
    min_value: float | None
    """Minimum allowed value for the parameter."""
    max_value: float | None
    """Maximum allowed value for the parameter."""
    allowed_values: list[Any] | None
    """Explicit list of allowed values (for ComboboxParameters), otherwise None."""
