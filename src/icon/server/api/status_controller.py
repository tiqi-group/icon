import asyncio

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.data_access.db_context import influxdb_v1
from icon.server.hardware_processing.hardware_controller import HardwareController
from icon.server.web_server.socketio_emit_queue import emit_queue


class StatusController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self.__hardware_controller = HardwareController(connect=False)
        self._influxdb_available = False
        self._hardware_available = False

    def get_status(self) -> dict[str, bool]:
        return {
            "influxdb": self._influxdb_available,
            "hardware": self._hardware_available,
        }

    def check_influxdb_status(self) -> None:
        status = influxdb_v1.is_responsive()

        self._influxdb_available = status
        emit_queue.put({"event": "status.influxdb", "data": status})

    async def check_hardware_status(self) -> None:
        if (
            not self.__hardware_controller.connected
            or self.__hardware_controller._host != get_config().hardware.host
            or self.__hardware_controller._port != get_config().hardware.port
        ):
            await asyncio.to_thread(self.__hardware_controller.connect)

        status = self.__hardware_controller.connected

        self._hardware_available = status
        emit_queue.put({"event": "status.hardware", "data": status})

    @task(autostart=True)
    async def check_status(self) -> None:
        while True:
            self.check_influxdb_status()
            await self.check_hardware_status()

            await asyncio.sleep(get_config().health_check.interval_seconds)
