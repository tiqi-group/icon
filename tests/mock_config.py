from icon.config.config import Config
from icon.config.latest import ServiceConfig


class MockConfig(Config):
    """A `Config` stand-in without any file-system access.

    `get()` returns the in-memory `ServiceConfig` instance; `set()` replaces it.
    """

    def __init__(self) -> None:
        self._config = ServiceConfig()

    def get(self) -> ServiceConfig:
        return self._config

    def set(self, config: ServiceConfig) -> None:
        self._config = config


def mock_config() -> MockConfig:
    """Return a new in-memory configuration mock."""
    return MockConfig()
