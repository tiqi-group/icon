import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from icon.config import latest
from icon.config.config import Config


@contextmanager
def temp_config() -> Iterator[Config]:
    """Yield a `Config` backed by a copy of the test config in a temp directory."""
    with TemporaryDirectory() as d:
        cfg_path = Path(d) / "config.yaml"
        shutil.copyfile(Path(__file__).parent.parent / "config.yaml", cfg_path)
        yield Config(cfg_path)


def test_config_loads_from_path() -> None:
    with temp_config() as config:
        service_config = config.get()
        assert service_config.version == latest.__version__
        expected_port = 8004
        assert service_config.server.port == expected_port
        assert service_config.date.timezone == "Europe/Zurich"


def test_config_is_thread_safe() -> None:  # noqa: C901
    """Concurrent `get()` and `set()` calls must not corrupt the shared state."""
    with temp_config() as config:
        errors: list[BaseException] = []

        def reader() -> None:
            try:
                for _ in range(100):
                    assert config.get().server.port > 0
            except BaseException as e:
                errors.append(e)

        first_port = 8004
        last_port = first_port + 5

        def writer() -> None:
            try:
                for port in range(first_port, last_port + 1):
                    new_config = config.get().model_copy(deep=True)
                    new_config.server.port = port
                    config.set(new_config)
            except BaseException as e:
                errors.append(e)

        threads = [threading.Thread(target=reader) for _ in range(4)]
        threads.append(threading.Thread(target=writer))
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, errors
        assert config.get().server.port == last_port
