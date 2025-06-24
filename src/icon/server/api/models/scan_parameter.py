from __future__ import annotations

from typing import Any, NotRequired, TypedDict


class ScanParameter(TypedDict):
    id: str
    """The parameter identifier. """
    values: list[Any]
    """List of explicit values to scan."""
    device_name: NotRequired[str]
    """Name of the device this parameter belongs to. None if variable lives in
    InfluxDB."""
