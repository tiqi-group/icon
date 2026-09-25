import asyncio
from typing import Any, TypedDict

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.data_access.db_context.influxdb import influxdb_v1
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.hardware_processing.devices import Devices, Hardware
from icon.server.web_server.socketio_emit_queue import emit_queue


class Error(TypedDict):
    msg: str


class HardwareStatus(TypedDict):
    display_name: str
    args: tuple[tuple[str, Any], ...]
    enabled: bool
    reachable: bool
    error: str | None
    warning: str | None


class Status(TypedDict):
    influxdb: bool
    hardware: list[HardwareStatus]


class StatusController(pydase.DataService):
    """Controller for system status monitoring.

    Periodically checks availability of InfluxDB and hardware and emits status events
    via the Socket.IO queue.
    """

    def __init__(
        self, devices: Devices, experiment_library_client: ExperimentLibraryClient
    ) -> None:
        super().__init__()
        self.__devices = devices
        self._influxdb_available = False
        self._experiment_library_client = experiment_library_client
        self._hardware_status: list[HardwareStatus] = []

    def get_status(self) -> Status:
        """Return the current system status flags.

        Returns:
            A dictionary with:

                - `"influxdb"`: Whether InfluxDB is responsive.
                - `"hardware"`: Whether the hardware connection is active.
        """
        return {
            "influxdb": self._influxdb_available,
            "hardware": self._hardware_status,
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
        await asyncio.to_thread(self.__devices.retry_disconnected)

        library_devices = set(await self._experiment_library_client.load_device_order())

        def make_warning(dev: Hardware) -> str | None:
            if dev.device_id is None:
                return None
            if dev.device_id not in library_devices and dev.enabled:
                return "Device is enabled but not used in the experiment library"
            if dev.device_id in library_devices and not dev.enabled:
                return "Device is disabled but required by the experiment library"
            return None

        status = [
            HardwareStatus(
                display_name=dev.display_name
                if isinstance(dev, Hardware)
                else cfg.display_name,
                enabled=cfg.enabled,
                args=cfg.args,
                reachable=isinstance(dev, Hardware) and dev.controller.connected,
                error=format(dev) if not isinstance(dev, Hardware) else None,
                warning=make_warning(dev) if isinstance(dev, Hardware) else None,
            )
            for cfg, dev in self.__devices.status()
        ]
        enabled_devices = set(self.__devices.enabled_ids())
        status += [
            HardwareStatus(
                display_name=name,
                enabled=False,
                args=(),
                reachable=False,
                error="Not reachable / not configured",
                warning=None,
            )
            for name in library_devices - enabled_devices
        ]
        self._hardware_status = status
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
