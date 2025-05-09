from pathlib import Path

from confz import BaseConfig
from pydantic import BaseModel


class ExperimentLibraryConfigV1(BaseModel):
    dir: str = str(Path(__file__).parent.parent.parent.parent)
    git_repository: str = "https://..."
    update_interval: int = 30


class ValkeyConfig(BaseModel):
    host: str = "localhost"
    port: int = 6379


class InfluxDBConfig(BaseModel):
    url: str = "http://localhost:8086"
    org: str = "test"
    token: str = "my-super-secret-auth-token"
    bucket: str = "Experiment parameters"


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
    valkey: ValkeyConfig = ValkeyConfig()
    influxdb: InfluxDBConfig = InfluxDBConfig()
    influxdbv1: InfluxDBv1Config = InfluxDBv1Config()


class DateConfig(BaseModel):
    timezone: str = "Europe/Zurich"


class IonpulsePluginConfig(BaseModel):
    host: str = "localhost"
    rpc_port: int = 8002
    web_port: int = 8003


class ServerConfig(BaseModel):
    port: int = 8004
    host: str = "0.0.0.0"


class ServiceConfigV1(BaseConfig):  # type: ignore[misc]
    version: int = 1
    experiment_library: ExperimentLibraryConfigV1 = ExperimentLibraryConfigV1()
    databases: DatabaseConfig = DatabaseConfig()
    ionpulse_plugin: IonpulsePluginConfig = IonpulsePluginConfig()
    date: DateConfig = DateConfig()
    server: ServerConfig = ServerConfig()
