"""
This file contains the scripts to migrate configurations from one version to another.
"""

from collections.abc import Callable
from typing import Any

from icon.config.v1 import ServiceConfigV1
from icon.config.v2 import ExperimentLibraryConfig
from icon.config.v2 import ServiceConfig as ServiceConfigV2

migration_by_version = {}


def migration(*, version: int) -> Callable[[Any], Any]:
    def decorate(f: Callable[[Any], Any]) -> Callable[[Any], Any]:
        migration_by_version[version] = f
        return f

    return decorate


@migration(version=1)
def migrate_v1_to_v2(old_config: ServiceConfigV1) -> ServiceConfigV2:
    exp_lib = old_config.experiment_library
    return ServiceConfigV2(
        experiment_library=ExperimentLibraryConfig(
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
