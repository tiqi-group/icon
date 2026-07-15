from __future__ import annotations

import asyncio
import logging
import multiprocessing
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.pycrystal_experiment_library_client import PyCrystalClient
from icon.server.data_access.repositories.experiment_data_repository import (
    ExperimentDataRepository,
)
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    job_run_cancelled_or_failed,
)
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)
from icon.server.data_access.venv_exec import VirtualEnvironment
from icon.server.pre_processing.worker import ExperimentIdentifier
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt

if TYPE_CHECKING:
    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.post_processing.task import PostProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager
    from icon.server.utils.types import UpdateQueue

logger = logging.getLogger(__name__)

QUEUE_POLL_TIMEOUT = 1.0
"""Seconds to block on the task queue before checking for finished jobs."""


@dataclass
class ExperimentPostProcessingState:
    """Per-job state of the experiment-defined post-processing."""

    post_processing_output: list[float] = field(default_factory=list)
    """State handed back by the experiment's post_processing on the last call."""
    pending_parameters: dict[str, DatabaseValueType] = field(default_factory=dict)
    """Parameters updated by post-processing but not yet uploaded to InfluxDB."""
    last_upload_time: float = field(default_factory=time.monotonic)
    """Monotonic timestamp of the last InfluxDB upload."""
    has_post_processing: bool | None = None
    """Whether the experiment defines post_processing (None until first call)."""


class PostProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        manager: SharedResourceManager,
        pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]],
    ) -> None:
        super().__init__()
        self._post_processing_queue = post_processing_queue
        self._manager = manager
        self._pre_processing_update_queues = pre_processing_update_queues
        self._job_states: dict[int, ExperimentPostProcessingState] = {}
        self._venvs: dict[str, VirtualEnvironment] = {}

    @handle_keyboard_interrupt(logger)
    def run(self) -> None:
        logger.info("Post-processing worker started")

        ParametersRepository.initialize(shared_parameters=self._manager.parameters_dict)

        while True:
            try:
                task = self._post_processing_queue.get(timeout=QUEUE_POLL_TIMEOUT)
            except queue.Empty:
                self._flush_finished_jobs()
                continue

            if not job_run_cancelled_or_failed(
                job_id=task.pre_processing_task.job.id,
            ):
                ExperimentDataRepository.write_experiment_data_by_job_id(
                    job_id=task.pre_processing_task.job.id,
                    data_point=task.data_point,
                )

                try:
                    self._run_experiment_post_processing(task)
                except Exception:
                    logger.exception(
                        "Experiment post-processing failed for job %s",
                        task.pre_processing_task.job.id,
                    )

            self._flush_finished_jobs()

    def _run_experiment_post_processing(self, task: PostProcessingTask) -> None:
        """Execute the experiment's optional post_processing for one data point.

        The experiment code runs inside the experiment library's virtual
        environment (the checkout that generated the data point). Parameters the
        experiment updates are pushed to running jobs immediately via
        "calibration" events and uploaded to InfluxDB at most every
        `db_upload_interval`; `_flush_finished_jobs` performs a final upload when
        the job ends.
        """
        job = task.pre_processing_task.job
        state = self._job_states.setdefault(job.id, ExperimentPostProcessingState())

        if state.has_post_processing is False or task.src_dir is None:
            return

        namespace = ExperimentIdentifier.from_str(job.experiment_source.experiment_id)

        # Same value source as sequence generation: the shared parameter dict,
        # overlaid with not-yet-uploaded post-processing updates and the scanned
        # values of this data point.
        parameter_dict: dict[str, DatabaseValueType] = {
            **ParametersRepository.get_shared_parameters(),
            **state.pending_parameters,
            **task.data_point.scan_params,
        }

        venv = self._venvs.get(task.src_dir)
        if venv is None:
            venv = VirtualEnvironment(str(Path(task.src_dir) / ".venv"))
            self._venvs[task.src_dir] = venv

        result = asyncio.run(
            venv.run(
                PyCrystalClient.run_experiment_post_processing,
                args={
                    "exp_module_name": namespace.module_name,
                    "exp_instance_name": namespace.instance_name,
                    "parameter_dict": parameter_dict,
                    "result_channels": task.data_point.result_channels,
                    "post_processing_output": state.post_processing_output,
                },
                logger=logger,
            )
        )

        state.has_post_processing = result["has_post_processing"]
        if not state.has_post_processing:
            return

        state.post_processing_output = result["post_processing_output"]

        updated_parameters: dict[str, DatabaseValueType] = result["updated_parameters"]
        if not updated_parameters:
            return

        logger.debug(
            "Post-processing of job %s updated parameters %s",
            job.id,
            updated_parameters,
        )
        state.pending_parameters.update(updated_parameters)

        # Push the new values into the running jobs right away; the pre-processing
        # workers merge them into their parameter dicts without a database query.
        for update_queue in self._pre_processing_update_queues:
            update_queue.put(
                {
                    "event": "calibration",
                    "new_parameters": updated_parameters,
                }
            )

        db_upload_interval = result["db_upload_interval"]  # seconds
        if db_upload_interval is not None and (
            time.monotonic() - state.last_upload_time >= db_upload_interval
        ):
            self._upload_pending_parameters(state)

    def _upload_pending_parameters(self, state: ExperimentPostProcessingState) -> None:
        """Upload pending parameter updates to shared state and InfluxDB."""
        if state.pending_parameters:
            ParametersRepository.update_parameters(
                parameter_mapping=dict(state.pending_parameters)
            )
            state.pending_parameters.clear()
        state.last_upload_time = time.monotonic()

    def _flush_finished_jobs(self) -> None:
        """Upload pending parameters of jobs that are no longer running."""
        for job_id in list(self._job_states):
            if JobRunRepository.get_run_by_job_id(job_id=job_id).status not in (
                JobRunStatus.PROCESSING,
                JobRunStatus.PAUSED,
            ):
                state = self._job_states.pop(job_id)
                self._upload_pending_parameters(state)
