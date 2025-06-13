import asyncio

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.api.configuration_controller import ConfigurationController
from icon.server.api.devices_controller import DevicesController
from icon.server.api.experiment_data_controller import ExperimentDataController
from icon.server.api.experiments_controller import ExperimentsController
from icon.server.api.parameters_controller import ParametersController
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.repositories.pycrystal_library_repository import (
    PycrystalLibraryRepository,
)


class APIService(pydase.DataService):
    scheduler = SchedulerController()
    experiments = ExperimentsController()
    parameters = ParametersController()
    config = ConfigurationController()
    data = ExperimentDataController()
    devices = DevicesController()

    @task(autostart=True)
    async def _update_experiment_and_parameter_metadata(self) -> None:
        while True:
            pycrystal_library_metadata = (
                await PycrystalLibraryRepository.get_experiment_and_parameter_metadata()
            )
            experiment_metadata = pycrystal_library_metadata["experiment_metadata"]
            parameter_metadata = pycrystal_library_metadata["parameter_metadata"]
            await self.parameters._create_missing_influxdb_entries(
                parameter_metadata=parameter_metadata
            )
            await self.experiments._update_experiment_metadata(
                experiment_metadata=experiment_metadata
            )
            await self.parameters._update_parameter_metadata_and_display_groups(
                parameter_metadata=parameter_metadata
            )
            await asyncio.sleep(get_config().experiment_library.update_interval)

    @task(autostart=True)
    async def _initialised_parameters(self) -> None:
        await self.parameters._initialise_valkey_cache()
