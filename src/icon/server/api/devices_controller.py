import logging
from typing import Any

import pydase
from pydase.utils.serialization.types import SerializedObject

from icon.serialization.deserializer import loads
from icon.serialization.serializer import dump
from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder

logger = logging.getLogger(__name__)

DeviceParameterValueyType = int | bool | float


def get_pydase_parameter_value(
    *, url: str, parameter_id: str
) -> SerializedObject | None:
    import requests

    response = requests.get(
        f"{url}/v1/get_value?access_path={parameter_id}",
    )
    if response.ok:
        return response.json()
    return None


def update_pydase_parameter_value(
    *, url: str, parameter_id: str, new_value: Any
) -> None:
    import requests

    response = requests.put(
        f"{url}/v1/update_value",
        data={
            "access_path": parameter_id,
            "value": dump(new_value),
        },
    )

    if not response.ok:
        logger.warning("Could not update parameter %s at %s", parameter_id, url)


class DevicesController(pydase.DataService):
    def add_device(
        self, *, name: str, url: str, description: str | None = None
    ) -> Device:
        return DeviceRepository.add_device(device=Device(name=name))

    def update_device_status(self, *, name: str, status: DeviceStatus) -> Device:
        return DeviceRepository.update_device_status(name=name, status=status)

    def update_parameter_value(
        self, *, name: str, parameter_id: str, new_value: DeviceParameterValueyType
    ) -> None:
        device = DeviceRepository.get_device_by_name(name=name)
        update_pydase_parameter_value(
            url=device.url, parameter_id=parameter_id, new_value=new_value
        )

    def get_parameter_value(self, *, name: str, parameter_id: str) -> Any:
        device = DeviceRepository.get_device_by_name(name=name)
        serialized_param_value = get_pydase_parameter_value(
            url=device.url, parameter_id=parameter_id
        )
        if serialized_param_value is not None:
            return loads(serialized_param_value)
        return None

    def get_devices_by_status(
        self, *, status: DeviceStatus | None = None
    ) -> dict[str, dict[str, Any]]:
        return {
            device.name: SQLAlchemyDictEncoder.encode(obj=device)
            for device in DeviceRepository.get_devices_by_status(status=status)
        }
