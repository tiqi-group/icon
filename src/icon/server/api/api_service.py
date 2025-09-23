from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pydase
import requests.exceptions
import urllib3.exceptions
from pydase.task.decorator import task

from icon.config.config import get_config
from icon.server.api.configuration_controller import ConfigurationController
from icon.server.api.devices_controller import DevicesController
from icon.server.api.experiment_data_controller import ExperimentDataController
from icon.server.api.experiments_controller import ExperimentsController
from icon.server.api.parameters_controller import ParametersController
from icon.server.api.scans_controller import ScansController
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.api.status_controller import StatusController
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.repositories.pycrystal_library_repository import (
    PycrystalLibraryRepository,
)

if TYPE_CHECKING:
    import multiprocessing

    from icon.server.utils.types import UpdateQueue

logger = logging.getLogger(__name__)


def _check_experiment_library_directory() -> bool:
    exp_lib_dir = get_config().experiment_library.dir
    if exp_lib_dir is None:
        logger.warning("Experiment library is not configured yet")
        return False
    if not Path(exp_lib_dir).exists():
        logger.warning("Experiment library directory %a does not exist", exp_lib_dir)
        return False
    return True


class APIService(pydase.DataService):
    """Aggregates ICON's API controllers and manages background tasks.

    The `APIService` groups multiple controllers, each of which is a
    `pydase.DataService` exposing related API methods. It also defines
    background tasks for keeping experiment and parameter metadata
    in sync with the experiment library and InfluxDB.

    Note:
         Controllers are `pydase.DataService` instances exposed as attributes to group
         related API methods. Background tasks are implemented with
         [`pydase` tasks](https://pydase.readthedocs.io/en/latest/user-guide/Tasks/).
    """

    def __init__(
        self, pre_processing_event_queues: list[multiprocessing.Queue[UpdateQueue]]
    ) -> None:
        """
        Args:
            pre_processing_event_queues: Queues used by `ScansController` to notify
                pre-processing workers.
        """

        super().__init__()

        self.devices = DevicesController()
        """Controller for managing external pydase-based devices."""
        self.scheduler = SchedulerController(devices_controller=self.devices)
        """Controller to submit, inspect, and cancel scheduled jobs."""
        self.experiments = ExperimentsController()
        """Controller for experiment metadata."""
        self.parameters = ParametersController()
        """Controller for parameter metadata and shared parameter values."""
        self.config = ConfigurationController()
        """Controller for managing and updating the application's configuration."""
        self.data = ExperimentDataController()
        """Controller for accessing stored experiment data."""
        self.scans = ScansController(
            pre_processing_update_queues=pre_processing_event_queues
        )
        """Controller for triggering update events for jobs across multiple worker
        processes."""
        self.status = StatusController()
        """Controller for system status monitoring."""

    @task(autostart=True)
    async def _update_experiment_and_parameter_metadata_task(self) -> None:
        while True:
            await self._update_experiment_and_parameter_metadata()

            await asyncio.sleep(get_config().experiment_library.update_interval)

    async def _update_experiment_and_parameter_metadata(self) -> None:
        if not _check_experiment_library_directory():
            return

        pycrystal_library_metadata = (
            await PycrystalLibraryRepository.get_experiment_and_parameter_metadata()
        )
        experiment_metadata = pycrystal_library_metadata["experiment_metadata"]
        parameter_metadata = pycrystal_library_metadata["parameter_metadata"]
        self.experiments._update_experiment_metadata(
            new_experiments=experiment_metadata
        )
        await self.parameters._update_parameter_metadata_and_display_groups(
            parameter_metadata=parameter_metadata
        )
        try:
            self.parameters._create_missing_influxdb_entries()
        except (
            urllib3.exceptions.MaxRetryError,
            requests.exceptions.ConnectionError,
        ):
            logger.warning(
                "InfluxDB is not available! Please check your configuration."
            )

    @task(autostart=True)
    async def _initialise_parameters_repository_task(self) -> None:
        """Periodically attempts to initialise the ParametersRepository until
        successful.
        """

        while not ParametersRepository.initialised:
            try:
                self.parameters.initialise_parameters_repository()
            except (
                urllib3.exceptions.MaxRetryError,
                requests.exceptions.ConnectionError,
            ):
                logger.warning(
                    "Failed to initialise ParametersRepository as InfluxDB is not "
                    "available. Retrying..."
                )

            await asyncio.sleep(5)
