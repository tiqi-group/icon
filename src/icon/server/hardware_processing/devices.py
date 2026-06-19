import importlib
from typing import TYPE_CHECKING, Any

from icon.config.reloader import DictReloader, ReloadError

if TYPE_CHECKING:
    from collections.abc import Iterable

    from icon.server.hardware_processing.hardware_controller import HardwareController


def load(
    controller_module: str, controller_class: str, id: str, **dev_args: Any
) -> "HardwareController":
    try:
        dev_module = importlib.import_module(controller_module)
        dev_class = getattr(dev_module, controller_class)
        return dev_class(**dev_args)
    except (ImportError, AttributeError) as e:
        raise ReloadError(
            f"Configuration for device {id} is invalid.\n"
            f"Error message: {e}\n"
            "Please reconfigure!"
        ) from None


class Devices:
    def __init__(self) -> None:
        self.__devices: dict[str, HardwareController] = {}
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
            if id(dev) in py_ids or not dev.connected:
                dev.connect()

    def __getitem__(self, dev_id: str) -> "HardwareController":
        self.reload()
        return self.__devices[dev_id]

    def items(self) -> "Iterable[tuple[str, HardwareController]]":
        self.reload()
        return self.__devices.items()

    def ids(self) -> "Iterable[str]":
        self.reload()
        return self.__devices.keys()
