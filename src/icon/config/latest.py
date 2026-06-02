from typing import Any

from confz import BaseConfig
from pydantic import BaseModel

from icon.config.v1 import (
    DatabaseConfig,
    DataConfiguration,
    DateConfig,
    HardwareConfig,
    HealthCheckConfig,
    ServerConfig,
)

__version__ = 2


class ExperimentLibraryConfig(BaseModel):
    module: str = "icon.server.data_access.pycrystal_experiment_library_client"
    client_class: str = "AsyncPyCrystalClient"
    client_args: dict[str, Any] = {}
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
