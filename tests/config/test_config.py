from icon.config.config import get_config_path
from tests.mock_config import mock_config


def test_get_config_path() -> None:
    with mock_config() as cfg_path:
        assert get_config_path() == cfg_path
