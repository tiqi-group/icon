from confz import BaseConfig
from pydantic import BaseModel

from icon.config.latest import (
    DatabaseConfig,
    DataConfiguration,
    DateConfig,
    ExperimentLibraryConfig,
    HealthCheckConfig,
    ServerConfig,
)

__version__ = 2


class HardwareConfig(BaseModel):
    host: str = "localhost"
    port: int = 6007


class ServiceConfig(BaseConfig):  # type: ignore[misc]
    version: int = __version__
    experiment_library: ExperimentLibraryConfig = ExperimentLibraryConfig()
    databases: DatabaseConfig = DatabaseConfig()
    date: DateConfig = DateConfig()
    server: ServerConfig = ServerConfig()
    hardware: HardwareConfig = HardwareConfig()
    health_check: HealthCheckConfig = HealthCheckConfig()
    data: DataConfiguration = DataConfiguration()
