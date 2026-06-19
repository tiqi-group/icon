import asyncio
from typing import TypedDict

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.data_access.db_context import influxdb_v1
from icon.server.hardware_processing.devices import Devices
from icon.server.web_server.socketio_emit_queue import emit_queue


class Status(TypedDict):
    influxdb: bool
    hardware: dict[str, bool]


class StatusController(pydase.DataService):
    """Controller for system status monitoring.

    Periodically checks availability of InfluxDB and hardware and emits status events
    via the Socket.IO queue.
    """

    def __init__(self, devices: Devices) -> None:
        super().__init__()
        self.__devices = devices
        self._influxdb_available = False
        self._hardware_available: dict[str, bool] = {}

    def get_status(self) -> Status:
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
        await asyncio.to_thread(self.__devices.reload)

        status = {dev_id: dev.connected for dev_id, dev in self.__devices.items()}
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
