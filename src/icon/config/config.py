import logging
import os
import threading
from pathlib import Path, PosixPath
from typing import Any

import yaml
from pydantic import BaseModel

from icon.config import latest, v1, v2
from icon.config.migrations import migration_by_version

logger = logging.getLogger("config")

VERSIONS: dict[int, type[BaseModel]] = {
    cfg.__version__: cfg.ServiceConfig for cfg in (v1, v2, latest)
}


class SubConfig:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.timestamp: int | None = None
        self.current_config: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        try:
            timestamp = os.stat(self.path).st_mtime_ns
        except FileNotFoundError:
            self.current_config = {}
            self.timestamp = None
            return {}
        if self.timestamp is not None and timestamp <= self.timestamp:
            return self.current_config
        with open(self.path, "rb") as f:
            self.current_config = yaml.safe_load(f)
            self.timestamp = timestamp
        return self.current_config


class Config:
    def __init__(self, path: Path | None = None) -> None:
        source = (
            (path or Path.home() / ".config" / "icon" / "config.yaml")
            .expanduser()
            .resolve()
        )
        self._lock = threading.Lock()
        self._main_config = SubConfig(source)
        self._hardware_config = SubConfig(source.parent / "hardware.yaml")
        if not source.is_file():
            source.parent.mkdir(parents=True, exist_ok=True)
            with source.open("a") as f:
                f.write(yaml.dump(latest.ServiceConfig().model_dump()))
        self._config = migrate_config(self._load_dict() or {}, source)

    def get(self) -> latest.ServiceConfig:
        with self._lock:
            self._load()
            return self._config

    def set(self, config: latest.ServiceConfig) -> None:
        with self._lock:
            self._config = config
            self._save()

    def _load_dict(self) -> dict[str, Any] | None:
        before = (self._main_config.timestamp, self._hardware_config.timestamp)
        main_config = self._main_config.load()
        hardware_config = self._hardware_config.load()
        after = (self._main_config.timestamp, self._hardware_config.timestamp)
        if before == after:
            return None
        # If hardware.yml exists, load it, otherwise use inline config:
        if hardware_config:
            main_config["hardware"] = hardware_config
        return main_config

    def _load(self) -> latest.ServiceConfig:
        config = self._load_dict()
        if config is not None:
            self._config = latest.ServiceConfig.model_validate(config)
        return self._config

    def _save(self) -> None:
        """Save the configuration to the source YAML file.

        Serializes the updated configuration and writes it back to the file.
        """
        full_config = self._config.model_dump()
        if self._hardware_config.timestamp is not None:
            hardware_config = full_config.pop("hardware")
            with self._hardware_config.path.open("w") as f:
                f.write(yaml.dump(hardware_config))
        with self._main_config.path.open("w") as f:
            f.write(yaml.dump(full_config))


def migrate_config(content: dict[str, Any], path: Path) -> latest.ServiceConfig:
    config_version = content.get("version")
    schema = VERSIONS.get(config_version) if config_version is not None else None
    if schema is None:
        raise RuntimeError(f"Unsupported configuration version: {config_version}")
    # The migration chain is dynamically typed (each step takes/returns the
    # versioned model of its era), so the intermediate config is `Any`.
    config: Any = schema.model_validate(content)
    original_config_version = config.version
    while config.version < latest.__version__:
        config = migration_by_version[config.version](config)
    if original_config_version < latest.__version__:
        logger.info(
            "Migrated config from verison %s to %s",
            original_config_version,
            latest.__version__,
        )
        with path.open("w") as f:
            f.write(yaml.dump(config.model_dump()))
    return config


# https://github.com/yaml/pyyaml/issues/617#issuecomment-1039273397
def path_representer(dumper: yaml.Dumper, data: Path) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.add_representer(PosixPath, path_representer)
