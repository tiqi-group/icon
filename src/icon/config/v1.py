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


class DatabaseConfig(BaseModel):
    valkey: ValkeyConfig = ValkeyConfig()
    influxdb: InfluxDBConfig = InfluxDBConfig()


class IonpulsePluginConfig(BaseModel):
    host: str = "localhost"
    rpc_port: int = 8002
    web_port: int = 8003


class ServiceConfigV1(BaseConfig):  # type: ignore[misc]
    version: int = 1
    experiment_library: ExperimentLibraryConfigV1 = ExperimentLibraryConfigV1()
    databases: DatabaseConfig = DatabaseConfig()
    ionpulse_plugin: IonpulsePluginConfig = IonpulsePluginConfig()
