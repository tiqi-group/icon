from __future__ import annotations

import asyncio
import dataclasses
import logging
import multiprocessing
import queue
from contextlib import ExitStack
from typing import TYPE_CHECKING, cast

from icon.server.data_access import venv_exec
from icon.server.data_access.experiment_data import Readouts
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    try_update_run_by_id,
)
from icon.server.pre_processing.worker import ExperimentIdentifier
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt

if TYPE_CHECKING:
    from icon.server.data_access.experiment_data import ExperimentDataPoint
    from icon.server.data_access.experiment_library_client import (
        ExperimentLibraryClient,
    )
    from icon.server.post_processing.task import PostProcessingTask

logger = logging.getLogger(__name__)

VENV_IDLE_TIMEOUT = 10.0
"""Seconds without data points after which the experiment library is unloaded."""


def add_derived_channels(
    data_point: ExperimentDataPoint, processed: ExperimentDataPoint
) -> ExperimentDataPoint:
    """Return `data_point` with the channels `processed` adds to its devices' readouts.

    The channels read out from the devices are read-only: their values in `processed`
    are ignored, as are devices `data_point` has no data of.
    """
    processed_readouts = {
        device_data.device_id: cast("Readouts", device_data.readouts)
        for device_data in processed.device_data
    }
    device_data = []
    for device in data_point.device_data:
        readouts = cast("Readouts", device.readouts)
        derived = processed_readouts.get(device.device_id)
        if derived is not None:
            readouts = Readouts(
                result_channels={**derived.result_channels, **readouts.result_channels},
                vector_channels={**derived.vector_channels, **readouts.vector_channels},
                shot_channels={**derived.shot_channels, **readouts.shot_channels},
            )
        device_data.append(dataclasses.replace(device, readouts=readouts))
    return dataclasses.replace(data_point, device_data=device_data)


class PostProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        experiment_library_client: ExperimentLibraryClient,
    ) -> None:
        super().__init__()
        self._post_processing_queue = post_processing_queue
        self._experiment_library_client = experiment_library_client
        # The library is kept loaded for the job run of the last data point
        self._kept_venv = ExitStack()
        self._run_id: int | None = None
        self._run_post_processes = False
        self._run_error_logged = False

    @handle_keyboard_interrupt(logger)
    def run(self) -> None:
        logger.info("Post-processing worker started")
        try:
            self._process_tasks()
        finally:
            self._forget_run()
            # So that the exit does not wait for a call still running, see
            # `venv_exec.shutdown`
            venv_exec.shutdown()

    def _process_tasks(self) -> None:
        while True:
            # Tasks of failed or cancelled jobs are still processed: they hold data
            # points measured before the job stopped, or the hardware instructions
            # of the data point that failed on the device.
            try:
                task = self._post_processing_queue.get(timeout=VENV_IDLE_TIMEOUT)
            except queue.Empty:
                # Don't keep the library loaded after the job run's last data point
                self._forget_run()
                continue

            try:
                ExperimentDataRepository.write_experiment_data_by_job_id(
                    job_id=task.pre_processing_task.job.id,
                    data_point=self._post_process(task),
                )
            except Exception as e:
                logger.exception(
                    "Post-processing of job with id '%s' failed",
                    task.pre_processing_task.job.id,
                )
                # Keep the status and log of runs that already failed or were
                # cancelled, e.g. the hardware error message.
                try_update_run_by_id(
                    run_id=task.pre_processing_task.job_run.id,
                    status=JobRunStatus.FAILED,
                    log=f"Post-processing error: {e}",
                    only_if_status=(
                        JobRunStatus.PROCESSING,
                        JobRunStatus.PAUSED,
                        JobRunStatus.DONE,
                    ),
                )

    def _post_process(self, task: PostProcessingTask) -> ExperimentDataPoint:
        """Return the task's data point with the channels its experiment derives.

        The experiment's `post_processing` runs in the experiment library, which is
        kept loaded for the calls of a job run, like in the pre-processing worker.

        If it fails, the error is logged to the job run, which goes on, and the data
        point is returned as read out, so its derived channels are stored as NaN.
        """
        data_point = task.data_point
        if data_point.failed:
            return data_point

        run_id = task.pre_processing_task.job_run.id
        if run_id != self._run_id:
            self._forget_run()
            self._run_id = run_id
            self._run_post_processes = True
            self._kept_venv.enter_context(self._experiment_library_client.reuse_venv())
        if not self._run_post_processes:
            return data_point

        experiment = ExperimentIdentifier.from_str(
            task.pre_processing_task.job.experiment_source.experiment_id
        )
        try:
            processed = asyncio.run(
                self._experiment_library_client.post_process(
                    exp_module_name=experiment.module_name,
                    exp_instance_name=experiment.instance_name,
                    parameter_dict=task.parameter_dict,
                    data_point=data_point,
                )
            )
        except Exception as e:
            logger.exception(
                "Post-processing of data point %d of job run %d failed",
                data_point.index,
                run_id,
            )
            self._log_error(
                task, f"Post-processing of data point {data_point.index}: {e}"
            )
            return data_point

        if processed is None:
            # The experiment defines no post-processing, so don't call it again
            self._run_post_processes = False
            self._kept_venv.close()
            return data_point
        return add_derived_channels(data_point, processed)

    def _forget_run(self) -> None:
        """Stop keeping the library loaded for the job run of the last data point."""
        self._kept_venv.close()
        self._run_id = None
        self._run_error_logged = False

    def _log_error(self, task: PostProcessingTask, error: str) -> None:
        """Log the first post-processing error of a job run to it, keeping its status.

        The log of a run that failed or was cancelled is kept, e.g. a hardware error.
        """
        if self._run_error_logged:
            return
        self._run_error_logged = True
        try:
            run = JobRunRepository.get_run_by_job_id(
                job_id=task.pre_processing_task.job.id
            )
        except Exception:
            logger.exception("Could not log the post-processing error to the job run")
            return
        if run.status in (
            JobRunStatus.PROCESSING,
            JobRunStatus.PAUSED,
            JobRunStatus.DONE,
        ):
            try_update_run_by_id(
                run_id=run.id,
                status=run.status,
                log=f"{error} (derived channels are stored as NaN where it failed)",
                only_if_status=(run.status,),
            )
