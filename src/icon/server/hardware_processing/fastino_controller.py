import logging

from icon.server.hardware_processing.hardware_controller import (
    FallbackHardwareController,
)

logger = logging.getLogger(__name__)


class FastinoController(FallbackHardwareController):
    """Placeholder for the Fastino Hardware Controller."""

    def __init__(self, device_id: str = "FastinoRack") -> None:
        super().__init__(device_id=device_id)
