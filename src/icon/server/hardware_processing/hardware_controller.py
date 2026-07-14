import logging
from enum import Enum, auto
from typing import Any

from icon.server.data_access.repositories.experiment_data_repository import ResultDict

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

    def send(self, data: Any) -> None:
        raise NotImplementedError("Must be implemented by a derived class")

    def run(self) -> None:
        raise NotImplementedError("Must be implemented by a derived class")

    def status(self) -> tuple[StatusFlag, str, Any]:
        raise NotImplementedError("Must be implemented by a derived class")

    def receive(self) -> ResultDict:
        raise NotImplementedError("Must be implemented by a derived class")


class FallbackHardwareController(HardwareController):
    """Noop hardware controller."""

    def connect(self) -> None:
        pass

    @property
    def connected(self) -> bool:
        return True

    def send(self, data: bytes) -> None:
        pass

    def run(self) -> None:
        pass

    def status(self) -> tuple[StatusFlag, str, Any]:
        return (StatusFlag.SUCCESS, "OK", ...)

    def receive(self) -> ResultDict:
        return ResultDict(result_channels={}, vector_channels={}, shot_channels={})
