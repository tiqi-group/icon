from pathlib import Path

from confz import BaseConfig
from pydantic import BaseModel


class HealthCheckConfig(BaseModel):
    interval_seconds: float = 10.0


class ExperimentLibraryConfigV1(BaseModel):
    dir: str = str(Path(__file__).parent.parent.parent.parent)
    git_repository: str = "https://..."
    update_interval: int = 30
    results_dir: str = str(Path(__file__).parent.parent.parent.parent / "output")


class InfluxDBv1Config(BaseConfig):  # type: ignore
    host: str = "localhost"
    port: int = 8086
    username: str = "admin"
    password: str = "admin"
    database: str = "testing"
    measurement: str = "Experiment Parameters"
    ssl: bool = True
    verify_ssl: bool = True
    headers: dict[str, str] = {}  # noqa: RUF012


class DatabaseConfig(BaseModel):
    influxdbv1: InfluxDBv1Config = InfluxDBv1Config()


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


class ServiceConfigV1(BaseConfig):  # type: ignore[misc]
    version: int = 1
    experiment_library: ExperimentLibraryConfigV1 = ExperimentLibraryConfigV1()
    databases: DatabaseConfig = DatabaseConfig()
    date: DateConfig = DateConfig()
    server: ServerConfig = ServerConfig()
    hardware: HardwareConfig = HardwareConfig()
    health_check: HealthCheckConfig = HealthCheckConfig()
