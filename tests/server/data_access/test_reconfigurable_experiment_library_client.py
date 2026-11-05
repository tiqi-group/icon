import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from icon.config import reloader
from icon.config.latest import ExperimentLibraryConfig
from icon.server.data_access.experiment_library_client import ExperimentLibraryClient
from icon.server.data_access.reconfigurable_experiment_library_client import (
    ReconfigurableExperimentLibraryClient,
)

EVENTS: list[tuple[str, str]] = []
"""What the clients of `_Client` did, by the name of the client."""


class _Client(ExperimentLibraryClient):
    """Client recording its calls and when it keeps the library loaded."""

    def __init__(self, name: str) -> None:
        self.name = name

    @contextmanager
    def reuse_venv(self) -> Iterator[None]:
        EVENTS.append((self.name, "enter reuse_venv"))
        try:
            yield
        finally:
            EVENTS.append((self.name, "exit reuse_venv"))

    async def load_device_order(self) -> list[str]:
        EVENTS.append((self.name, "load_device_order"))
        return [self.name]


@pytest.fixture
def configure(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    """Configure the experiment library client to be a `_Client` of a name."""
    config = SimpleNamespace()

    def configure(name: str) -> None:
        config.experiment_library = ExperimentLibraryConfig(
            module=__name__, client_class=_Client.__name__, client_args={"name": name}
        )

    monkeypatch.setattr(reloader, "get_config", lambda: config)
    yield configure
    EVENTS.clear()


def test_reused_venv_keeps_its_client_when_the_config_changes(
    configure: Callable[[str], None],
) -> None:
    configure("old")
    client = ReconfigurableExperimentLibraryClient()

    with client.reuse_venv():
        configure("new")
        assert asyncio.run(client.load_device_order()) == ["old"]

    assert EVENTS == [
        ("old", "enter reuse_venv"),
        ("old", "load_device_order"),
        ("old", "exit reuse_venv"),
    ]
    assert asyncio.run(client.load_device_order()) == ["new"]


def test_pinned_client_is_the_one_of_the_config_on_entry(
    configure: Callable[[str], None],
) -> None:
    configure("old")
    client = ReconfigurableExperimentLibraryClient()
    configure("new")

    with client.pinned():
        configure("newer")
        with client.reuse_venv():
            asyncio.run(client.load_device_order())
        assert asyncio.run(client.load_device_order()) == ["new"]

    assert {name for name, _ in EVENTS} == {"new"}
    assert asyncio.run(client.load_device_order()) == ["newer"]
