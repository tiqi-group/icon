from pathlib import Path

from icon.config.config import set_config_path

set_config_path(Path(__file__).parent / "config.yaml")
