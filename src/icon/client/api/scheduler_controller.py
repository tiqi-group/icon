import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from icon.server.api.models.experiment import Experiment

if TYPE_CHECKING:
    from icon.client.client import Client

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class JobProxy:
    def __init__(self, *, client: "Client", job_id: int) -> None:
        self._client = client
        self._job_id = job_id
        self._getting_data = False

    def toggle_plot(self) -> None:
        if not self._getting_data:
            connection_future = asyncio.run_coroutine_threadsafe(
                self._subscribe_to_experiment_data_stream(), self._client._loop
            )
            connection_future.result()
        else:
            connection_future = asyncio.run_coroutine_threadsafe(
                self._unsubscribe_from_experiment_data_stream(), self._client._loop
            )
            connection_future.result()

    async def _unsubscribe_from_experiment_data_stream(self) -> None:
        await self._client._sio.emit("stop_experiment_data_stream", self._job_id)
        self._getting_data = False

    async def _subscribe_to_experiment_data_stream(self) -> None:
        await self._client._sio.emit("get_experiment_data", self._job_id)
        self._getting_data = True


class SchedulerController:
    def __init__(self, client: "Client") -> None:
        self._client = client

    def submit_job(
        self,
        *,
        experiment: Experiment,
        priority: int,
        local_parameters_timestamp: datetime,
        # scan_info: ScanInfo,
        repetitions: int = 1,
    ) -> JobProxy:
        job_id: int = self._client.trigger_method(
            "scheduler.submit_job",
            kwargs={
                "experiment": experiment,
                "priority": priority,
                "local_parameters_timestamp": local_parameters_timestamp,
                # "scan_info": scan_info,
                "repetitions": repetitions,
            },
        )
        return JobProxy(client=self._client, job_id=job_id)
