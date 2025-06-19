import asyncio
import logging
from typing import Any, Literal

import pydase
from socketio.exceptions import BadNamespaceError  # type: ignore

from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.repositories.device_repository import DeviceRepository

logger = logging.getLogger(__name__)

DeviceParameterValueyType = int | bool | float


class DevicesController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self._initialise_devices()

    def add_device(
        self,
        *,
        name: str,
        url: str,
        status: Literal["disabled", "enabled"] = "enabled",
        description: str | None = None,
    ) -> Device:
        device = DeviceRepository.add_device(
            device=Device(
                name=name, url=url, status=DeviceStatus(status), description=description
            )
        )

        if status == "enabled":
            self._devices[name] = pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )

        return device

    def update_device_status(
        self,
        *,
        name: str,
        status: Literal["disabled", "enabled"],
    ) -> Device:
        device = DeviceRepository.update_device_status(
            name=name, status=DeviceStatus(status)
        )

        if status == "disabled" and name in self._devices:
            del self._devices[name]
        elif status == "enabled":
            self._devices[name] = pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )

        return device

    async def update_parameter_value(
        self, *, name: str, parameter_id: str, new_value: DeviceParameterValueyType
    ) -> None:
        try:
            await asyncio.to_thread(
                self._devices[name].update_value(
                    access_path=parameter_id, new_value=new_value
                )
            )
        except BadNamespaceError:
            logger.warning(
                'Could not set %r. Device %r at ("%s") is not connected.',
                parameter_id,
                name,
                self._devices[name]._url,
            )

    async def get_parameter_value(self, *, name: str, parameter_id: str) -> Any:
        try:
            return await asyncio.to_thread(
                self._devices[name].get_value(access_path=parameter_id)
            )
        except BadNamespaceError:
            logger.warning(
                'Could not get %r. Device %r at ("%s") is not connected.',
                parameter_id,
                name,
                self._devices[name]._url,
            )

    def get_devices_by_status(
        self, *, status: DeviceStatus | None = None
    ) -> dict[str, Device]:
        return {
            device.name: device
            for device in DeviceRepository.get_devices_by_status(status=status)
        }

    def _initialise_devices(self) -> None:
        devices = DeviceRepository.get_devices_by_status(status=DeviceStatus.ENABLED)
        self._devices: dict[str, pydase.Client] = {
            device.name: pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )
            for device in devices
        }
