from __future__ import annotations

from typing import Any

import sys
if sys.version_info < (3, 11):
    from typing_extensions import NotRequired
else:
    from typing import NotRequired

if sys.version_info < (3, 12):
    from typing_extensions import TypedDict
else:
    from typing import TypedDict


class ScanParameter(TypedDict):
    """Specification of a parameter to scan during a job."""

    id: str
    """Unique identifier of the parameter."""

    values: list[Any]
    """List of explicit values to scan for this parameter."""

    device_name: NotRequired[str]
    """Name of the device this parameter belongs to.

    If omitted, the parameter is assumed to be stored in InfluxDB.
    """
