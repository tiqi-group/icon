from confz import BaseConfig
from pydantic import BaseModel

from icon.config.latest import (
    DatabaseConfig,
    DataConfiguration,
    DateConfig,
    HardwareConfig,
    HealthCheckConfig,
    ServerConfig,
)

__version__ = 1


class ExperimentLibraryConfig(BaseModel):
    dir: str | None = None
    git_repository: str = "https://..."
    update_interval: int = 30


class ServiceConfig(BaseConfig):  # type: ignore[misc]
    version: int = __version__
    experiment_library: ExperimentLibraryConfig = ExperimentLibraryConfig()
    databases: DatabaseConfig = DatabaseConfig()
    date: DateConfig = DateConfig()
    server: ServerConfig = ServerConfig()
    hardware: HardwareConfig = HardwareConfig()
    health_check: HealthCheckConfig = HealthCheckConfig()
    data: DataConfiguration = DataConfiguration()
