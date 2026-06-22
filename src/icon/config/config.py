import logging
import os
from contextlib import suppress
from pathlib import Path, PosixPath

import yaml
from confz import BaseConfig, FileSource

from icon.config import latest, v1, v2
from icon.config.migrations import migration_by_version

_ENV_KEY = "ICON_CONFIG"

logger = logging.getLogger("config")

VERSIONS: dict[int, BaseConfig] = {
    cfg.__version__: cfg.ServiceConfig for cfg in (v1, v2, latest)
}


# https://github.com/yaml/pyyaml/issues/617#issuecomment-1039273397
def path_representer(dumper: yaml.Dumper, data: Path) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.add_representer(PosixPath, path_representer)


def get_config() -> latest.ServiceConfig:
    source = get_config_path()

    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        with source.open("a") as f:
            f.write(yaml.dump(latest.ServiceConfig().model_dump()))

    with source.open("r") as f:
        content = yaml.safe_load(f)
        config_version = content.get("version", None)

    # If hardware.yml exists, load it, otherwise use inline config:
    with suppress(FileNotFoundError), _hardware_config_path(source).open("r") as f:
        hw_content = yaml.safe_load(f)
        content["hardware"] = hw_content

    schema = VERSIONS.get(config_version)
    if schema is None:
        raise RuntimeError(f"Unsupported configuration version: {config_version}")
    config = schema(config_sources=FileSource(source))
    original_config_version = config.version
    while config.version < latest.__version__:
        config = migration_by_version[config.version](config)
    if original_config_version < latest.__version__:
        logger.info(
            "Migrated config from verison %s to %s",
            original_config_version,
            latest.__version__,
        )
        with source.open("w") as file:
            file.write(yaml.dump(config.model_dump()))

    return config


def save_config(config: latest.ServiceConfig) -> None:
    """Save the configuration to the source YAML file.

    Serializes the updated configuration and writes it back to the file.

    Args:
        config:
            The validated configuration instance.
    """
    source = get_config_path()
    full_config = config.model_dump()
    hardware_config_path = _hardware_config_path(source)
    if hardware_config_path.exists():
        hardware_config = full_config.pop("hardware")
        with hardware_config_path.open("w") as f:
            f.write(yaml.dump(hardware_config))
    with source.open("w") as f:
        f.write(yaml.dump(full_config))


def _normalize(p: str | Path) -> Path:
    return Path(p).expanduser().resolve()


def set_config_path(p: Path) -> None:
    """Set once at startup; children inherit via environment."""
    os.environ[_ENV_KEY] = str(_normalize(p))


def get_config_path() -> Path:
    """Read from env, else default."""
    if env := os.environ.get(_ENV_KEY):
        return _normalize(env)
    return _normalize(Path.home() / ".config/icon/config.yaml")


def _hardware_config_path(config_path: Path) -> Path:
    return config_path.parent / "hardware.yaml"
