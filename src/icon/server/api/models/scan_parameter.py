from __future__ import annotations

import sys
from typing import Any, TypedDict

from typing_extensions import NotRequired

if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired


class ScanParameter(TypedDict):
    parameter: str
    """The parameter identifier. """
    values: dict[str, Any] | list[Any]
    """ Either a dictionary with 'start', 'stop', and 'num_points' keys or a list of
    explicit values. """
    randomized: NotRequired[bool]
    """Boolean indicating whether the values should be shuffled."""
    reversed: NotRequired[bool]
    """Boolean indicating whether the values should be reversed."""
