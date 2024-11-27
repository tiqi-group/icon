from pathlib import Path

from confz import BaseConfig
from pydantic import BaseModel


class ExperimentLibraryConfigV1(BaseModel):
    dir: Path = Path(__file__).parent.parent.parent.parent
    git_repository: str = "https://..."
    update_interval: int = 30


class ServiceConfigV1(BaseConfig):  # type: ignore[misc]
    version: int = 1
    experiment_library: ExperimentLibraryConfigV1 = ExperimentLibraryConfigV1()
