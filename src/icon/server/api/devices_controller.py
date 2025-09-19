import asyncio
import logging
from typing import TYPE_CHECKING, Any, Literal

import pydase
import pydase.units as u
from pydase.task.decorator import task
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
"""Allowed primitive types for device parameter values.

A parameter value sent to or retrieved from a device may be one of these
basic types. Quantities with units are handled separately via `pydase.units.Quantity`.
"""


class DevicesController(pydase.DataService):
    """Controller for managing external pydase-based devices.

    Maintains client connections to configured devices, exposes helpers to
    add/update device entries in SQLite, and provides async accessors for device
    parameter values through pydase proxies. Also discovers scannable device parameters
    for integration with ICON scans.
    """

    def __init__(self) -> None:
        super().__init__()
        self._devices: dict[str, pydase.Client] = {}
        self.device_proxies: dict[str, ProxyClass] = {}
        """Live pydase proxies keyed by device name."""

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
        """Create a device record in SQLite and (optionally) connect to it.

        If `status=="enabled"`, a non-blocking pydase client is created and its
        proxy is registered.

        Args:
            name: Unique device name.
            url: pydase server URL of the device.
            status: Whether the device should be connected immediately.
            description: Optional human-readable description.
            retry_delay_seconds: Backoff delay used by device-side logic.
            retry_attempts: Number of retries used by device-side logic.

        Returns:
            The `Device` SQLAlchemy model.
        """

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
        """Update a device record and its live connection.

        When transitioning to `disabled`, the client is disconnected and removed.
        When transitioning to `enabled`, a client is (re)created and registered.

        Args:
            name: Device name.
            status: Target enable/disable status.
            url: Updated pydase URL.
            retry_attempts: Updated retry attempts metadata.
            retry_delay_seconds: Updated retry delay metadata.

        Returns:
            The updated `Device` model.
        """

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
        self,
        *,
        name: str,
        parameter_id: str,
        new_value: DeviceParameterValueyType | u.QuantityDict,
        type_: Literal["float", "int", "Quantity"],
    ) -> None:
        """Set a parameter value on a connected device.

        Performs type-normalization (`float`, `int`, or `Quantity`) before delegating
        to the device client.

        Logs a warning if the device is not connected or not found.

        Args:
            name: Device name.
            parameter_id: Access path on the device service.
            new_value: New value (native type or quantity dict).
            type_: Expected type of the value for normalization.
        """

        if type_ == "float" and not isinstance(new_value, dict):
            new_value = float(new_value)
        elif type_ == "int" and not isinstance(new_value, dict):
            new_value = int(new_value)
        elif type_ == "Quantity" and isinstance(new_value, dict):
            new_value = u.Quantity(new_value["magnitude"], new_value["unit"])  # type: ignore

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
        """Get a parameter value from a connected device.

        Logs a warning if the device is not connected or not found.

        Args:
            name: Device name.
            parameter_id: Access path on the device service.

        Returns:
            The parameter value as returned by the device, or `None` if the device is
                unreachable or unknown.
        """

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
        """List devices (optionally filtered by status) with reachability & scan info.

        Augments each device entry with

        - `reachable`: Whether a live proxy is connected.
        - `scannable_params`: Flat list of scannable parameter access paths.

        Args:
            status: Optional filter (`ENABLED`, `DISABLED`, or `None` for all).

        Returns:
            Mapping from device name to a `DeviceDict` payload suitable for the API.
        """

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

    @task(autostart=True)
    async def _initialise_devices(self) -> None:
        """Background task: connect clients for all ENABLED devices on startup.

        Fetches ENABLED devices from SQLite and creates non-blocking pydase clients and
        proxies for each of them.
        """

        devices = DeviceRepository.get_devices_by_status(status=DeviceStatus.ENABLED)

        for device in devices:
            client = pydase.Client(
                url=device.url,
                client_id="icon-devices-controller",
                block_until_connected=False,
            )
            self._devices[device.name] = client
            self.device_proxies[device.name] = client.proxy
