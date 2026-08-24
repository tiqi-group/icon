import logging
from typing import Any

from icon.server.data_access.experiment_data import Readouts
from icon.server.hardware_processing.hardware_controller import (
    HardwareController,
    StatusFlag,
)
from icon.server.hardware_processing.rpc import rfsoc

logger = logging.getLogger(__name__)


class RFSoCController(HardwareController):
    def __init__(
        self, *, host: str, port: int, timeout: int = 5, cached: bool = True
    ) -> None:
        """Initialise the controller.

        Args:
            host: Hostname of the RFSoC.
            port: Port the RFSoC RPC server listens on.
            timeout: RPC timeout in seconds for calls such as runExperiment. Configurable
                in the config file.
            cached: Whether to read the channel names out of the sequence description
                instead of asking the device for them after every run. Saves three round
                trips per data point.
        """
        self._host = host
        self._port = port
        self._timeout = timeout
        self._rfsoc = (rfsoc.RFSoCSeqRunnerCached if cached else rfsoc.RFSoCSeqRunner)(
            hostname=self._host, port=self._port, timeout=timeout
        )

    def connect(self) -> None:
        try:
            self._rfsoc.connect()
        except rfsoc.RFSoCError as e:
            logger.warning(
                "Connected to %r, but it may not be configured properly sequence running: %s",
                self._rfsoc,
                e,
            )
        except (ConnectionResetError, ConnectionRefusedError, OSError) as e:
            logger.warning("Could not connect to the RFSoC: %s (%r)", e, self._rfsoc)
        else:
            logger.info("Connected to the RFSoC: %s", self._rfsoc)

    @property
    def connected(self) -> bool:
        """RFSoC is ready to process sequences."""
        return self._rfsoc.is_connected

    def send(self, data: str) -> None:
        if not self.connected:
            self.connect()
        if not self.connected:
            raise RuntimeError(
                f"Could not connect to the RFSoC at {self._host}:{self._port} "
                f"while trying to run a command"
            )
        self._rfsoc.load_sequence(data)

    def run(self) -> None:
        """The sequence is executed in the :meth:`receive` call. Nothing to be done here."""

    def receive(self) -> Readouts:
        results = self._rfsoc.run_sequence()

        return Readouts(
            result_channels=results.result_channels,
            vector_channels=results.vector_channels,
            shot_channels=results.shot_channels,
        )

    def status(self) -> tuple[StatusFlag, str, Any]:
        return (StatusFlag.UNKNOWN, "", None)
