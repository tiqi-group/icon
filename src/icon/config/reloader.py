import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from icon.config.config import get_config

if TYPE_CHECKING:
    from icon.config.latest import ServiceConfig

logger = logging.getLogger(__name__)


class ReloadError(Exception):
    pass


class Reloader:
    def __init__(
        self,
        obj_factory: Callable[..., Any],
        fallback_obj: Any,
        subconfig: "Callable[[ServiceConfig], dict[str, Any]]",
    ) -> None:
        self.current_config: dict[str, Any] = {}
        self.obj_factory = staticmethod(obj_factory)
        self.obj = fallback_obj
        self.fallback_obj = fallback_obj
        self.subconfig = staticmethod(subconfig)

    def reload(self) -> Any:
        new_config = self.subconfig(get_config())
        if new_config == self.current_config:
            return self.obj
        try:
            self.obj = self.obj_factory(**new_config)
        except ReloadError as e:
            logger.warning(format(e))
            self.obj = self.fallback_obj

        self.current_config = new_config
        return self.obj

    def is_configured(self) -> bool:
        return self.obj is not self.fallback_obj


class DictReloader:
    def __init__(
        self,
        initial_objs: dict[str, Any],
        obj_factory: Callable[..., Any],
        subconfig: "Callable[[ServiceConfig], dict[str, Any]]",
    ) -> None:
        self.current_config: dict[str, Any] = {}
        self.obj_factory = staticmethod(obj_factory)
        self.objs = initial_objs
        self.subconfig = staticmethod(subconfig)

    def reload_changed(self) -> list[Any]:
        new_config = self.subconfig(get_config())
        changed_or_new = [
            (key, args)
            for key, args in new_config.items()
            if args != self.current_config.get(key)
        ]
        for key, args in changed_or_new:
            try:
                self.objs[key] = self.obj_factory(**args)
            except ReloadError as e:
                logger.warning(format(e))
                del self.objs[key]
        for removed in set(self.objs) - set(new_config):
            del self.objs[removed]
        self.current_config = new_config
        return [self.objs[key] for key, _ in changed_or_new]
