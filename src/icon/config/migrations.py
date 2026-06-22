"""This file contains the scripts to migrate configurations from one version to another."""

from collections.abc import Callable
from typing import Any

from icon.config import latest as v3
from icon.config import v1, v2

migration_by_version = {}


def migration(*, version: int) -> Callable[[Any], Any]:
    def decorate(f: Callable[[Any], Any]) -> Callable[[Any], Any]:
        migration_by_version[version] = f
        return f

    return decorate


@migration(version=1)
def migrate_v1_to_v2(old_config: v1.ServiceConfig) -> v2.ServiceConfig:
    exp_lib = old_config.experiment_library
    return v2.ServiceConfig(
        experiment_library=v2.ExperimentLibraryConfig(
            update_interval=exp_lib.update_interval,
            client_args={
                "checkout_path": exp_lib.dir,
                "repo": exp_lib.git_repository,
            },
        ),
        databases=old_config.databases,
        date=old_config.date,
        server=old_config.server,
        hardware=old_config.hardware,
        health_check=old_config.health_check,
        data=old_config.data,
    )


@migration(version=2)
def migrate_v2_to_v3(old_config: v2.ServiceConfig) -> v3.ServiceConfig:
    hw_config = old_config.hardware
    return v3.ServiceConfig(
        experiment_library=old_config.experiment_library,
        databases=old_config.databases,
        date=old_config.date,
        server=old_config.server,
        hardware=v3.HardwareConfig(
            devices=[
                v3.DeviceConfig(
                    id="zedboard",
                    controller_module="icon.server.hardware_processing.zedboard_controller",
                    controller_class="ZedboardController",
                    host=hw_config.host,
                    port=hw_config.port,
                )
            ]
        ),
        health_check=old_config.health_check,
        data=old_config.data,
    )
