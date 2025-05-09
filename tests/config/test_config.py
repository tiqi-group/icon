from pathlib import Path

from icon.config.config import get_config_source


def test_get_config_source() -> None:
    assert get_config_source() == Path(__file__).parent.parent / "config.yaml"
