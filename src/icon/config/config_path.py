from __future__ import annotations

import os
from pathlib import Path

_ENV_KEY = "ICON_CONFIG"


def _normalize(p: str | Path) -> Path:
    return Path(p).expanduser().resolve()


def set_config_path(p: Path) -> None:
    """Set once at startup; children inherit via environment."""
    os.environ[_ENV_KEY] = str(_normalize(p))


def get_config_path() -> Path:
    """Read from env, else default."""
    if env := os.environ.get(_ENV_KEY):
        return _normalize(env)
    return _normalize(Path.home() / ".config/icon/config.yaml")
