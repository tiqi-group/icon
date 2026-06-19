import logging
from typing import Any

try:
    import tiqi_zedboard.zedboard
except ImportError:
    raise ImportError(
        "Tiqi zedboard package is not available. Please enable the `zedboard` extra."
    ) from None


from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.hardware_controller import (
    HardwareController,
    StatusFlag,
)
from icon.server.utils.sockets import is_socket_closed

logger = logging.getLogger(__name__)


class ZedboardController(HardwareController):
    def __init__(self, *, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._zedboard: tiqi_zedboard.zedboard.Zedboard | None = None

    def connect(self) -> None:
        logger.info("Connecting to the Zedboard")
        self._zedboard = tiqi_zedboard.zedboard.Zedboard(
            hostname=self._host, port=self._port
        )
        if not self.connected:
            logger.warning("Failed to connect to the Zedboard")

    @property
    def connected(self) -> bool:
        return (
            self._zedboard is not None
            and getattr(self._zedboard, "_client", None) is not None
            and not is_socket_closed(self._zedboard._client._socket)
        )

    def _update_zedboard_sequence(self, *, sequence: str) -> None:
        if self._zedboard is not None:
            self._zedboard.sequence_JSON_parser.Sequence_JSON = sequence  # type: ignore

    def send(self, data: bytes) -> None:
        if not self.connected:
            self.connect()
        if not self.connected:
            raise RuntimeError("Could not connect to the Zedboard")
        self._update_zedboard_sequence(sequence=data.decode())

    def run(self) -> None:
        self._zedboard.sequence_JSON_parser.Parse_JSON_Header()  # type: ignore

    def receive(self) -> Readouts:
        results: tiqi_zedboard.zedboard.Result = self._zedboard.sequence_JSON_parser()  # type: ignore

        return Readouts(
            result_channels=results.result_channels,
            vector_channels=results.vector_channels
            if results.vector_channels is not None
            else {},
            shot_channels=results.shot_channels,
        )

    def status(self) -> tuple[StatusFlag, str, Any]:
        return (StatusFlag.UNKNOWN, "", None)
