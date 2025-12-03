from pathlib import Path

from icon.config.config import get_config_path


def test_get_config_path() -> None:
    assert get_config_path() == Path(__file__).parent.parent / "config.yaml"
