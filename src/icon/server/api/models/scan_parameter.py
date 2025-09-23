from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RealtimeParameter:
    """Specification of the realtime parameter to scan during a job."""

    n_scan_points: int
    """Number of discrete scan points.

    If `0`, the scan is continuous.
    """


@dataclass
class DatabaseParameter:
    """Specification of a database parameter to scan during a job."""

    id: str
    """Unique identifier of the parameter."""

    values: list[float | int | bool | str]
    """List of explicit values to scan for this parameter."""


@dataclass
class DeviceParameter:
    """Specification of a device parameter to scan during a job."""

    id: str
    """Unique identifier of the parameter."""

    values: list[float | int]
    """List of explicit values to scan for this parameter."""

    device_name: str
    """Name of the device this parameter belongs to."""


ScanParameter = DeviceParameter | DatabaseParameter | RealtimeParameter


def scan_parameter_from_dict(param: dict[str, Any]) -> ScanParameter:
    if "n_scan_points" in param:
        param.pop("values", None)
        param.pop("id", None)
        return RealtimeParameter(**param)
    if "device_name" in param:
        return DeviceParameter(**param)
    return DatabaseParameter(**param)
