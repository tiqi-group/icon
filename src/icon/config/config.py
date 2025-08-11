from pathlib import Path, PosixPath

import yaml
from confz import FileSource

from icon.config.config_path import get_config_path
from icon.config.v1 import ServiceConfigV1


# https://github.com/yaml/pyyaml/issues/617#issuecomment-1039273397
def path_representer(dumper: yaml.Dumper, data: Path) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data))


yaml.add_representer(PosixPath, path_representer)


def get_config() -> ServiceConfigV1:
    source = get_config_path()

    if not source.is_file():
        source.parent.mkdir(parents=True, exist_ok=True)
        with source.open("a") as file:
            file.write(yaml.dump(ServiceConfigV1().model_dump()))

    with source.open("r") as file:
        content = yaml.safe_load(file)
        config_version = content.get("version", None)

    if config_version == 1:
        config = ServiceConfigV1(config_sources=FileSource(source))
    else:
        raise Exception('Configuration version has to be "1"')

    return config
