import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from icon.config.reloader import DictReloader, ReloadError
from icon.server.hardware_processing.hardware_controller import HardwareController


@dataclass
class Hardware:
    controller: HardwareController | ReloadError
    enabled: bool


def load(
    controller_module: str,
    controller_class: str,
    id: str,
    args: dict[str, Any],
    *,
    enabled: bool,
) -> Hardware:
    try:
        dev_module = importlib.import_module(controller_module)
        dev_class = getattr(dev_module, controller_class)
        return Hardware(controller=dev_class(**args), enabled=enabled)
    except (ImportError, AttributeError) as e:
        return Hardware(
            controller=ReloadError(
                f"Configuration for device {id} is invalid.\n"
                f"Error message: {e}\n"
                "Please reconfigure!"
            ),
            enabled=enabled,
        )


class Devices:
    def __init__(self) -> None:
        self.__devices: dict[str, Hardware] = {}
        self.__reloader = DictReloader(
            initial_objs=self.__devices,
            obj_factory=load,
            subconfig=lambda config: {
                dev["id"]: dev for dev in config.hardware.model_dump()["devices"]
            },
        )

    def reload(self) -> None:
        reloaded_devices = self.__reloader.reload_changed()
        py_ids = {id(dev) for dev in reloaded_devices}
        # Reconnect changed / new / disconnected:
        for dev in self.__devices.values():
            if isinstance(dev.controller, HardwareController) and (
                id(dev) in py_ids or not dev.controller.connected
            ):
                dev.controller.connect()

    def __getitem__(self, dev_id: str) -> Hardware:
        self.reload()
        return self.__devices[dev_id]

    def items(self) -> Iterable[tuple[str, Hardware]]:
        self.reload()
        return self.__devices.items()

    def enabled_ids(self) -> list[str]:
        self.reload()
        return [id for id, dev in self.__devices.items() if dev.enabled]
