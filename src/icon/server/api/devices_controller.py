import logging
from typing import Any

import pydase

from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder

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
        status: DeviceStatus = DeviceStatus.ENABLED,
        description: str | None = None,
    ) -> Device:
        return DeviceRepository.add_device(
            device=Device(name=name, url=url, status=status, description=description)
        )

    def update_device_status(self, *, name: str, status: DeviceStatus) -> Device:
        return DeviceRepository.update_device_status(name=name, status=status)

    def update_parameter_value(
        self, *, name: str, parameter_id: str, new_value: DeviceParameterValueyType
    ) -> None:
        self._devices[name].update_value(access_path=parameter_id, new_value=new_value)

    def get_parameter_value(self, *, name: str, parameter_id: str) -> Any:
        return self._devices[name].get_value(access_path=parameter_id)

    def get_devices_by_status(
        self, *, status: DeviceStatus | None = None
    ) -> dict[str, dict[str, Any]]:
        return {
            device.name: SQLAlchemyDictEncoder.encode(obj=device)
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
