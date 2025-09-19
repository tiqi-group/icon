import asyncio

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.data_access.db_context import influxdb_v1
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.web_server.socketio_emit_queue import emit_queue


class StatusController(pydase.DataService):
    """Controller for system status monitoring.

    Periodically checks availability of InfluxDB and hardware and emits status events
    via the Socket.IO queue.
    """

    def __init__(self) -> None:
        super().__init__()
        self.__hardware_controller = HardwareController(connect=False)
        self._influxdb_available = False
        self._hardware_available = False

    def get_status(self) -> dict[str, bool]:
        """Return the current system status flags.

        Returns:
            A dictionary with:

                - `"influxdb"`: Whether InfluxDB is responsive.
                - `"hardware"`: Whether the hardware connection is active.
        """

        return {
            "influxdb": self._influxdb_available,
            "hardware": self._hardware_available,
        }

    def check_influxdb_status(self) -> None:
        """Check if InfluxDB is responsive and update status.

        Emits a `"status.influxdb"` event to the Socket.IO queue.
        """

        status = influxdb_v1.is_responsive()

        self._influxdb_available = status
        emit_queue.put({"event": "status.influxdb", "data": status})

    async def check_hardware_status(self) -> None:
        """Check hardware connection and reconnect if necessary.

        Ensures the hardware controller matches the configured host/port and reconnects
        in a background thread if required.

        Emits a `"status.hardware"` event to the Socket.IO queue.
        """

        status = self.__hardware_controller.connected

        if (
            not status
            or self.__hardware_controller._host != get_config().hardware.host
            or self.__hardware_controller._port != get_config().hardware.port
        ):
            await asyncio.to_thread(self.__hardware_controller.connect)

        self._hardware_available = status
        emit_queue.put({"event": "status.hardware", "data": status})

    @task(autostart=True)
    async def _check_status(self) -> None:
        """Background task that periodically checks system status.

        Runs an infinite loop that:

        - Updates InfluxDB status.
        - Updates hardware status.
        - Sleeps for the configured health check interval.
        """

        while True:
            self.check_influxdb_status()
            await self.check_hardware_status()

            await asyncio.sleep(get_config().health_check.interval_seconds)
