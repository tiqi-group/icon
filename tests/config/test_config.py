import pydantic
import pytest

from icon.config.config import get_config_path
from icon.config.latest import PreProcessingConfig
from tests.mock_config import mock_config


def test_get_config_path() -> None:
    with mock_config() as cfg_path:
        assert get_config_path() == cfg_path


@pytest.mark.parametrize("queue_size", [0, -1])
def test_pre_processing_queue_size_must_be_positive(queue_size: int) -> None:
    with pytest.raises(pydantic.ValidationError):
        PreProcessingConfig(queue_size=queue_size)
