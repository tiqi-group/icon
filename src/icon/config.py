from pathlib import Path

from confz import BaseConfig, EnvSource  # type: ignore


class ServiceConfig(BaseConfig):  # type: ignore[misc]
    experiment_library_dir: Path
    experiment_library_repository: str

    CONFIG_SOURCES = EnvSource(allow_all=True, prefix="SERVICE_", file=".env")
