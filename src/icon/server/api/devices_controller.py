import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

import pydase
from socketio.exceptions import BadNamespaceError  # type: ignore

from icon.server.api.models.device_dict import DeviceDict
from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder

if TYPE_CHECKING:
    from pydase.client.proxy_class import ProxyClass

logger = logging.getLogger(__name__)

DeviceParameterValueyType = int | bool | float


class DevicesController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self._devices: dict[str, pydase.Client] = {}
        self._device_proxies: dict[str, ProxyClass] = {}
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
            client = pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )
            self._devices[name] = client
            self._device_proxies[name] = client.proxy

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
            del self._device_proxies[name]
        elif status == "enabled":
            client = pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )
            self._devices[name] = client
            self._device_proxies[device.name] = client.proxy

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
        except KeyError:
            logger.warning("Device with name %r not found. Is it enabled?", name)

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
        except KeyError:
            logger.warning("Device with name %r not found. Is it enabled?", name)

    def get_devices_by_status(
        self, *, status: DeviceStatus | None = None
    ) -> dict[str, DeviceDict]:
        device_dict: dict[str, DeviceDict] = {
            device.name: SQLAlchemyDictEncoder.encode(device)
            for device in DeviceRepository.get_devices_by_status(status=status)
        }

        for name, value in device_dict.items():
            client = self._devices.get(name, None)
            value["reachable"] = client.proxy.connected if client is not None else False

        return device_dict

    def _initialise_devices(self) -> None:
        devices = DeviceRepository.get_devices_by_status(status=DeviceStatus.ENABLED)

        for device in devices:
            client = pydase.Client(
                url=device.url,
                client_id="ICON-devices-controller",
                block_until_connected=False,
            )
            self._devices[device.name] = client
            self._device_proxies[device.name] = client.proxy
