import asyncio
import logging
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import TYPE_CHECKING, Any

import matplotlib.pyplot as plt
import pandas as pd

from icon.client.api.helpers.notebook import in_notebook
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
            self._start_plot()
        else:
            self._stop_plot()

    async def _unsubscribe_from_experiment_data_stream(self) -> None:
        await self._client._sio.emit("stop_experiment_data_stream", self._job_id)

    async def _subscribe_to_experiment_data_stream(self) -> None:
        await self._client._sio.emit("get_experiment_data", self._job_id)

        # this has to stay here - otherwise, the notebooks won't show the plot
        self._client._loop.create_task(self._run_plot())

    def _start_plot(self) -> None:
        logger.info("Starting plot")
        self._getting_data = True
        connection_future = asyncio.run_coroutine_threadsafe(
            self._subscribe_to_experiment_data_stream(), self._client._loop
        )
        connection_future.result()

    def _stop_plot(self) -> None:
        logger.info("Stopping plot")
        self._getting_data = False
        connection_future = asyncio.run_coroutine_threadsafe(
            self._unsubscribe_from_experiment_data_stream(), self._client._loop
        )
        connection_future.result()

    async def _run_plot(self) -> None:
        self._fig, self._ax = plt.subplots()
        (self._line,) = self._ax.plot([], [], "r-")  # Initialize a line object
        self._ax.set_xlim(0, 1)  # You might want to adjust these limits
        self._ax.set_ylim(-1, 1)  # You might want to adjust these limits
        self._ax.grid()
        plt.ion()
        plt.show()

        async for data_frame in self._get_frame():
            self._update_plot(data_frame)
            if in_notebook():
                # otherwise, it will only update when hovering with the mouse
                self._fig.canvas.draw_idle()
            else:
                self._fig.canvas.flush_events()

            if not self._getting_data:
                break

            await asyncio.sleep(0.01)  # Control animation speed

    async def _get_frame(self) -> AsyncGenerator[pd.DataFrame | None, None]:
        logger.debug("Getting Frame")

        current_data: pd.DataFrame | None = None
        previous_length = 0

        while True:
            current_data = self._client._experiment_job_data.get(self._job_id)
            current_length = len(current_data.index) if current_data is not None else 0
            if current_length > previous_length:
                logger.debug("Yielding new frame")
                previous_length = current_length
                yield current_data
            else:
                await asyncio.sleep(0.1)

    def _update_plot(self, data_frame: pd.DataFrame | None) -> Any:
        if data_frame is not None:
            self._line.set_data(data_frame.iloc[:, 0], data_frame.iloc[:, 1])
        return (self._line,)


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

    def get_job_by_id(
        self,
        *,
        job_id: int,
    ) -> JobProxy:
        return JobProxy(client=self._client, job_id=job_id)
