from typing import TypedDict


class DeviceDict(TypedDict):
    """Dictionary representation of a device returned by the API."""

    id: int
    """Database identifier of the device."""
    created: str
    """Creation timestamp in ISO format."""
    name: str
    """Unique device name."""
    url: str
    """pydase server URL of the device."""
    status: str
    """Device status, e.g. "enabled" or "disabled"."""
    description: str | None
    """Optional human-readable description."""
    reachable: bool
    """Whether the device is currently connected."""
    scannable_params: list[str]
    """List of scannable parameter access paths."""
