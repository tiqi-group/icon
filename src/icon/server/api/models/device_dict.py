from typing import TypedDict


class DeviceDict(TypedDict):
    id: int
    created: str
    name: str
    url: str
    status: str
    description: str | None
    reachable: bool
