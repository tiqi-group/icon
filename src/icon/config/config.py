import logging
from pathlib import Path, PosixPath

import yaml
from confz import BaseConfig, FileSource

from icon.config import v1
from icon.config import v2 as latest
from icon.config.config_path import get_config_path
from icon.config.migrations import migration_by_version

logger = logging.getLogger("config")

VERSIONS: dict[int, BaseConfig] = {1: v1.ServiceConfigV1, 2: latest.ServiceConfig}


# https://github.com/yaml/pyyaml/issues/617#issuecomment-1039273397
def path_representer(dumper: yaml.Dumper, data: Path) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.add_representer(PosixPath, path_representer)


def get_config() -> latest.ServiceConfig:
    source = get_config_path()

    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        with source.open("a") as file:
            file.write(yaml.dump(latest.ServiceConfig().model_dump()))

    with source.open("r") as file:
        content = yaml.safe_load(file)
        config_version = content.get("version", None)

    schema = VERSIONS.get(config_version)
    if schema is None:
        raise RuntimeError("Unsupported configuration version: {config_version}")
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
