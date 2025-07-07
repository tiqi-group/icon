import logging

import tiqi_zedboard.zedboard  # type: ignore

from icon.config.config import get_config
from icon.server.data_access.repositories.experiment_data_repository import ResultDict
from icon.server.utils.sockets import is_socket_closed

logger = logging.getLogger(__name__)


class HardwareController:
    def __init__(self, connect: bool = True) -> None:
        self._host = get_config().hardware.host
        self._port = get_config().hardware.port
        self._zedboard: tiqi_zedboard.zedboard.Zedboard | None = None
        if connect:
            self.connect()

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
            and hasattr(self._zedboard, "_client")
            and self._zedboard._client is not None
            and not is_socket_closed(self._zedboard._client._socket)
        )

    def _update_zedboard_sequence(self, *, sequence: str) -> None:
        if self._zedboard is not None:
            self._zedboard.sequence_JSON_parser.Sequence_JSON = sequence  # type: ignore

    def _update_number_of_shots(self, *, number_of_shots: int) -> None:
        if self._zedboard is not None:
            self._zedboard.sequence_JSON_parser.Shots = number_of_shots  # type: ignore

    def run(self, *, sequence: str, number_of_shots: int) -> ResultDict:
        if not self.connected:
            self.connect()

        if not self.connected:
            raise RuntimeError("Could not connect to the Zedboard")

        self._update_zedboard_sequence(sequence=sequence)
        self._update_number_of_shots(number_of_shots=number_of_shots)
        self._zedboard.sequence_JSON_parser.Parse_JSON_Header()  # type: ignore
        results: tiqi_zedboard.zedboard.Result = self._zedboard.sequence_JSON_parser()  # type: ignore

        return {
            "result_channels": results.result_channels,
            "vector_channels": results.vector_channels
            if results.vector_channels is not None
            else {},
            "shot_channels": results.shot_channels,
        }
