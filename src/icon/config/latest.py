from pathlib import Path
from typing import Any, Literal

from confz import BaseConfig
from pydantic import BaseModel

__version__ = 2


class HealthCheckConfig(BaseModel):
    interval_seconds: float = 10.0


class DataConfiguration(BaseModel):
    results_dir: str = str(Path.cwd() / "output")


class ExperimentLibraryConfig(BaseModel):
    module: str = "icon.server.data_access.pycrystal_experiment_library_client"
    client_class: str = "AsyncPyCrystalClient"
    client_args: dict[str, Any] = {}
    update_interval: int = 30


class InfluxDBv1Config(BaseModel):
    host: str = "localhost"
    port: int = 8087
    username: str = "admin"
    password: str = "admin"  # noqa: S105
    database: str = "testing"
    measurement: str = "Experiment Parameters"
    ssl: bool = False
    verify_ssl: bool = False
    headers: dict[str, str] = {}


class InfluxDBv2Config(BaseModel):
    url: str = "http://localhost:8086"
    token: str = ""
    org: str = ""
    bucket: str = "testing"
    measurement: str = "Experiment Parameters"
    verify_ssl: bool = True


class SQLiteConfig(BaseModel):
    file: str = str(Path.cwd() / "icon.db")


class DatabaseConfig(BaseModel):
    backend: Literal["influxdbv1", "influxdbv2"] = "influxdbv1"
    influxdbv1: InfluxDBv1Config = InfluxDBv1Config()
    influxdbv2: InfluxDBv2Config = InfluxDBv2Config()
    sqlite: SQLiteConfig = SQLiteConfig()


class DateConfig(BaseModel):
    timezone: str = "Europe/Zurich"


class PreProcessingConfig(BaseModel):
    workers: int = 2


class ServerConfig(BaseModel):
    port: int = 8004
    host: str = "0.0.0.0"
    pre_processing: PreProcessingConfig = PreProcessingConfig()


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
