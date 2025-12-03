from pathlib import Path

from icon.config.config_path import set_config_path

set_config_path(Path(__file__).parent / "config.yaml")
