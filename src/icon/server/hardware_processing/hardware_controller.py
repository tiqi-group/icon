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
