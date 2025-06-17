from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import pydase
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.api.configuration_controller import ConfigurationController
from icon.server.api.devices_controller import DevicesController
from icon.server.api.experiment_data_controller import ExperimentDataController
from icon.server.api.experiments_controller import ExperimentsController
from icon.server.api.parameters_controller import ParametersController
from icon.server.api.scans_controller import ScansController
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.repositories.pycrystal_library_repository import (
    PycrystalLibraryRepository,
)

if TYPE_CHECKING:
    import multiprocessing


class APIService(pydase.DataService):
    def __init__(
        self, pre_processing_update_queues: list[multiprocessing.Queue[dict[str, Any]]]
    ) -> None:
        super().__init__()

        self.scheduler = SchedulerController()
        self.experiments = ExperimentsController()
        self.parameters = ParametersController()
        self.config = ConfigurationController()
        self.data = ExperimentDataController()
        self.devices = DevicesController()
        self.scans = ScansController(
            pre_processing_update_queues=pre_processing_update_queues
        )

    @task(autostart=True)
    async def _update_experiment_and_parameter_metadata(self) -> None:
        while True:
            pycrystal_library_metadata = (
                await PycrystalLibraryRepository.get_experiment_and_parameter_metadata()
            )
            experiment_metadata = pycrystal_library_metadata["experiment_metadata"]
            parameter_metadata = pycrystal_library_metadata["parameter_metadata"]
            self.parameters._create_missing_influxdb_entries(
                parameter_metadata=parameter_metadata
            )
            self.experiments._update_experiment_metadata(
                new_experiments=experiment_metadata
            )
            await self.parameters._update_parameter_metadata_and_display_groups(
                parameter_metadata=parameter_metadata
            )
            await asyncio.sleep(get_config().experiment_library.update_interval)
