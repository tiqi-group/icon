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

    def check_influxdb_status(self) -> None:
        emit_queue.put(
            {"event": "status.influxdb", "data": influxdb_v1.is_responsive()}
        )

    async def check_hardware_status(self) -> None:
        if not self.__hardware_controller.connected:
            await asyncio.to_thread(self.__hardware_controller.connect)

        emit_queue.put(
            {"event": "status.hardware", "data": self.__hardware_controller.connected}
        )

    @task(autostart=True)
    async def check_status(self) -> None:
        while True:
            self.check_influxdb_status()
            await self.check_hardware_status()

            await asyncio.sleep(get_config().health_check.interval_seconds)
