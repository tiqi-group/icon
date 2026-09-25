import importlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Generic, Self, TypeVar

from icon.config.config import get_config
from icon.config.reloader import ReloadError
from icon.server.hardware_processing.hardware_controller import HardwareController

if TYPE_CHECKING:
    from icon.config.latest import DeviceConfig, ServiceConfig

logger = logging.getLogger(__name__)


@dataclass
class Hardware:
    controller: HardwareController
    enabled: bool
    device_id: str | None = None

    def connect(self) -> None:
        self.controller.connect()
        self.device_id = self.controller.query_device_id()

    @property
    def display_name(self) -> str:
        if self.device_id is not None:
            return self.device_id
        return self.controller.display_name


@dataclass(frozen=True)
class FrozenHardwareConfig:
    controller_module: str
    controller_class: str
    enabled: bool
    args: tuple[tuple[str, Any], ...]

    @classmethod
    def from_config(cls, cfg: "DeviceConfig") -> Self:
        def freeze_dict(d: dict[str, Any]) -> tuple[tuple[str, Any], ...]:
            return tuple(sorted(d.items()))

        return cls(
            args=freeze_dict(cfg.args),
            controller_module=cfg.controller_module,
            controller_class=cfg.controller_class,
            enabled=cfg.enabled,
        )

    @property
    def display_name(self) -> str:
        arg_repr = ", ".join((f"{key}={val}" for key, val in self.args))
        return f"{self.controller_class}({arg_repr})"

    def load(self) -> Hardware:
        try:
            dev_module = importlib.import_module(self.controller_module)
            dev_class = getattr(dev_module, self.controller_class)
            return Hardware(
                controller=dev_class(**dict(self.args)), enabled=self.enabled
            )
        except (ImportError, AttributeError) as e:
            raise ReloadError(
                f"Configuration for device {self.controller_module}.{self.display_name} is invalid.\n"
                f"Error message: {e}\n"
                "Please reconfigure!"
            ) from e


class Devices:
    def __init__(self) -> None:
        self.__enabled_devices: dict[str, Hardware] = {}
        self.__reloader = ListReloader(
            obj_factory=FrozenHardwareConfig.load,
            subconfig=lambda config: [
                FrozenHardwareConfig.from_config(cfg) for cfg in config.hardware.devices
            ],
        )

    def reload(self, *, retry_disconnected: bool = False) -> None:
        reloaded_devices = {id(dev): dev for dev in self.__reloader.reload_changed()}
        if retry_disconnected:
            reloaded_devices.update(
                {
                    id(dev): dev
                    for dev in self.__reloader.objs
                    if isinstance(dev, Hardware)
                    if not dev.controller.connected
                }
            )
        for dev in reloaded_devices.values():
            dev.connect()
        self.__enabled_devices = {
            dev.device_id: dev
            for dev in self.__reloader.objs
            if isinstance(dev, Hardware) and dev.device_id is not None and dev.enabled
        }

    def retry_disconnected(self) -> None:
        self.reload(retry_disconnected=True)

    def __getitem__(self, dev_id: str) -> Hardware:
        self.reload()
        return self.__enabled_devices[dev_id]

    def enabled_ids(self) -> list[str]:
        self.reload()
        return [id for id, dev in self.__enabled_devices.items()]

    def status(self) -> list[tuple[FrozenHardwareConfig, Hardware | ReloadError]]:
        return list(zip(self.__reloader.config, self.__reloader.objs, strict=True))


C = TypeVar("C")
T = TypeVar("T")


class ListReloader(Generic[C, T]):
    """Use the items of whatever subconfig returns as a reference for what changes."""

    def __init__(
        self,
        obj_factory: Callable[[C], T],
        subconfig: "Callable[[ServiceConfig], list[C]]",
    ) -> None:
        # Mapping from frozen config to item index in `initial_objs`:
        self.obj_factory = staticmethod(obj_factory)
        self.config: list[C] = []
        self.objs: list[T | ReloadError] = []
        self.subconfig = staticmethod(subconfig)

    def reload_changed(self) -> Iterable[T]:
        current_objs = dict(zip(self.config, self.objs, strict=True))
        self.config = self.subconfig(get_config())
        self.objs.clear()
        for cfg in self.config:
            current = current_objs.get(cfg)
            if current is not None:
                self.objs.append(current)
                continue
            try:
                new_obj = self.obj_factory(cfg)
                yield new_obj
                self.objs.append(new_obj)
            except ReloadError as e:
                self.objs.append(e)
