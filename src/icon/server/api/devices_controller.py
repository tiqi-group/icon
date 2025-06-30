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
from icon.server.utils.scannable_device_parameters import get_scannable_params_list

if TYPE_CHECKING:
    from pydase.client.proxy_class import ProxyClass

logger = logging.getLogger(__name__)

DeviceParameterValueyType = int | bool | float


class DevicesController(pydase.DataService):
    def __init__(self) -> None:
        super().__init__()
        self._devices: dict[str, pydase.Client] = {}
        self.device_proxies: dict[str, ProxyClass] = {}
        self._initialise_devices()

    def add_device(  # noqa: PLR0913
        self,
        *,
        name: str,
        url: str,
        status: Literal["disabled", "enabled"] = "enabled",
        description: str | None = None,
        retry_delay_seconds: float = 0.0,
        retry_attempts: int = 3,
    ) -> Device:
        device = DeviceRepository.add_device(
            device=Device(
                name=name,
                url=url,
                status=DeviceStatus(status),
                description=description,
                retry_delay_seconds=retry_delay_seconds,
                retry_attempts=retry_attempts,
            )
        )

        if status == "enabled":
            client = pydase.Client(
                url=device.url,
                client_id="icon-devices-controller",
                block_until_connected=False,
            )
            self._devices[name] = client
            self.device_proxies[name] = client.proxy

        return device

    def update_device(
        self,
        *,
        name: str,
        status: Literal["disabled", "enabled"] | None = None,
        url: str | None = None,
        retry_attempts: int | None = None,
        retry_delay_seconds: float | None = None,
    ) -> Device:
        device = DeviceRepository.update_device(
            name=name,
            url=url,
            status=DeviceStatus(status) if status is not None else None,
            retry_attempts=retry_attempts,
            retry_delay_seconds=retry_delay_seconds,
        )

        if status == "disabled" and name in self._devices:
            if name in self.device_proxies:
                self.device_proxies.pop(name)
            if name in self._devices:
                client = self._devices.pop(name)
                client.disconnect()
        elif status == "enabled":
            client = pydase.Client(
                url=device.url,
                client_id="icon-devices-controller",
                block_until_connected=False,
            )
            self._devices[name] = client
            self.device_proxies[device.name] = client.proxy

        return device

    async def update_parameter_value(
        self, *, name: str, parameter_id: str, new_value: DeviceParameterValueyType
    ) -> None:
        try:
            await asyncio.to_thread(
                self._devices[name].update_value,
                access_path=parameter_id,
                new_value=new_value,
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
                self._devices[name].get_value, access_path=parameter_id
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
            value["reachable"] = False
            value["scannable_params"] = []

            if client is not None:
                value["reachable"] = client.proxy.connected
                value["scannable_params"] = get_scannable_params_list(
                    client.proxy.serialize(),
                    prefix=f'devices.device_proxies["{name}"].',
                )

        return device_dict

    def _initialise_devices(self) -> None:
        devices = DeviceRepository.get_devices_by_status(status=DeviceStatus.ENABLED)

        for device in devices:
            client = pydase.Client(
                url=device.url,
                client_id="icon-devices-controller",
                block_until_connected=False,
            )
            self._devices[device.name] = client
            self.device_proxies[device.name] = client.proxy
