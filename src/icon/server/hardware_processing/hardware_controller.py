import tiqi_zedboard.zedboard  # type: ignore

from icon.config.config import get_config
from icon.server.data_access.repositories.experiment_data_repository import ResultDict


class HardwareController:
    def __init__(self) -> None:
        self._host = get_config().hardware.host
        self._port = get_config().hardware.port
        self._zedboard: tiqi_zedboard.zedboard.Zedboard = (
            tiqi_zedboard.zedboard.Zedboard(hostname=self._host, port=self._port)
        )

    def _update_zedboard_sequence(self, *, sequence: str) -> None:
        self._zedboard.sequence_JSON_parser.Sequence_JSON = sequence  # type: ignore

    def _update_number_of_shots(self, *, number_of_shots: int) -> None:
        self._zedboard.sequence_JSON_parser.Shots = number_of_shots  # type: ignore

    def run(self, *, sequence: str, number_of_shots: int) -> ResultDict:
        self._update_zedboard_sequence(sequence=sequence)
        self._update_number_of_shots(number_of_shots=number_of_shots)
        results: tiqi_zedboard.zedboard.Result = self._zedboard.sequence_JSON_parser()  # type: ignore

        return {
            "result_channels": results.result_channels,
            "vector_channels": results.vector_channels
            if results.vector_channels is not None
            else {},
            "shot_channels": results.shot_channels,
        }
