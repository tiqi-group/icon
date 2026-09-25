import logging
from enum import Enum, auto
from typing import Any

from icon.server.data_access.experiment_data import Readouts

logger = logging.getLogger(__name__)


class StatusFlag(Enum):
    SUCCESS = auto()
    ERROR = auto()
    UNKNOWN = auto()


class HardwareController:
    def connect(self) -> None:
        raise NotImplementedError("Must be implemented by a derived class")

    @property
    def connected(self) -> bool:
        raise NotImplementedError("Must be implemented by a derived class")

    @property
    def display_name(self) -> str:
        """Representative name which also must be available when the device is not reachable.

        The return value should uniquely identify a device to an end user (e.g. ip adress, port).
        """
        arg_repr = ", ".join(f"{key}={val}" for key, val in vars(self).items())
        return f"{type(self).__name__}({arg_repr})"

    def query_device_id(self) -> str | None:
        """Query the id from a connected device."""
        raise NotImplementedError("Must be implemented by a derived class")

    def send(self, data: str) -> None:
        raise NotImplementedError("Must be implemented by a derived class")

    def run(self) -> None:
        raise NotImplementedError("Must be implemented by a derived class")

    def status(self) -> tuple[StatusFlag, str, Any]:
        raise NotImplementedError("Must be implemented by a derived class")

    def receive(self) -> Readouts:
        raise NotImplementedError("Must be implemented by a derived class")


class FallbackHardwareController(HardwareController):
    """Noop hardware controller."""

    def __init__(self, device_id: str = "FallbackHardware") -> None:
        self._device_id = device_id

    def connect(self) -> None:
        pass

    @property
    def connected(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        """Representative name which also must be available when the device is not reachable."""
        return self._device_id

    def query_device_id(self) -> str | None:
        return self._device_id

    def send(self, data: str) -> None:
        pass

    def run(self) -> None:
        pass

    def status(self) -> tuple[StatusFlag, str, Any]:
        return (StatusFlag.SUCCESS, "OK", ...)

    def receive(self) -> Readouts:
        return Readouts(result_channels={}, vector_channels={}, shot_channels={})
