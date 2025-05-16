from __future__ import annotations

from typing import Any, TypedDict


class ScanParameter(TypedDict):
    id: str
    """The parameter identifier. """
    values: dict[str, Any] | list[Any]
    """ Either a dictionary with 'start', 'stop', and 'num_points' keys or a list of
    explicit values. """
