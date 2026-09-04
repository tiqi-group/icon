import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from icon.config.config import set_config_path


@contextmanager
def mock_config() -> Iterator[Path]:
    cfg_path_original = Path(__file__).parent / "config.yaml"

    with TemporaryDirectory() as d:
        cfg_path = Path(d) / "config.yaml"
        set_config_path(cfg_path)
        shutil.copyfile(cfg_path_original, cfg_path)
        yield cfg_path
