from __future__ import annotations

import asyncio
import logging
import multiprocessing
import queue
import time
from contextlib import ExitStack
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, TypeVar

from icon.server.data_access.experiment_data import PostProcessingOutput
from icon.server.data_access.models.enums import JobRunStatus
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
from icon.server.pre_processing.worker import ExperimentIdentifier
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from icon.server.data_access.db_context.influxdb_v1 import DatabaseValueType
    from icon.server.data_access.experiment_library_client import (
        ExperimentLibraryClient,
    )
    from icon.server.post_processing.task import PostProcessingTask
    from icon.server.shared_resource_manager import SharedResourceManager
    from icon.server.utils.types import UpdateQueue

logger = logging.getLogger(__name__)

QUEUE_POLL_TIMEOUT = 1.0
"""Seconds to block on the task queue before checking for finished jobs."""

T = TypeVar("T")


@dataclass
class ExperimentPostProcessingState:
    """Per-job state of the experiment-defined post-processing."""

    post_processing_output: PostProcessingOutput = field(
        default_factory=PostProcessingOutput
    )
    """State handed back by the experiment's post_processing on the last call."""
    pending_parameters: dict[str, DatabaseValueType] = field(default_factory=dict)
    """Parameters updated by post-processing but not yet uploaded to InfluxDB."""
    last_upload_time: float = field(default_factory=time.monotonic)
    """Monotonic timestamp of the last InfluxDB upload."""
    has_post_processing: bool | None = None
    """Whether the experiment defines post_processing (None until first call)."""
    client: ExperimentLibraryClient | None = None
    """Client checked out to this job's revision, reused for its data points."""
    client_stack: ExitStack = field(default_factory=ExitStack)
    """Owns `client`'s isolation context (if any); closed once the job ends."""


class PostProcessingWorker(multiprocessing.Process):
    def __init__(
        self,
        post_processing_queue: multiprocessing.Queue[PostProcessingTask],
        manager: SharedResourceManager,
        pre_processing_update_queues: list[multiprocessing.Queue[UpdateQueue]],
        experiment_library_client: ExperimentLibraryClient,
    ) -> None:
        super().__init__()
        self._post_processing_queue = post_processing_queue
        self._manager = manager
        self._pre_processing_update_queues = pre_processing_update_queues
        self._experiment_library_client = experiment_library_client
        self._job_states: dict[int, ExperimentPostProcessingState] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    @handle_keyboard_interrupt(logger)
    def run(self) -> None:
        logger.info("Post-processing worker started")

        ParametersRepository.initialize(shared_parameters=self._manager.parameters_dict)

        # A single event loop is kept alive for the whole process, rather
        # than using `asyncio.run` per task, so that a job's persistent
        # experiment-library worker subprocess (started on its first data
        # point -- see `ExperimentPostProcessingState`) stays usable for its
        # later data points instead of being tied to a loop that's already
        # closed by the time they arrive.
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        while True:
            try:
                task = self._post_processing_queue.get(timeout=QUEUE_POLL_TIMEOUT)
            except queue.Empty:
                self._flush_finished_jobs()
                continue

            if not job_run_cancelled_or_failed(
                job_id=task.pre_processing_task.job.id,
            ):
                # Post-processing runs first so that result channels it fills in
                # are part of the stored data point; on failure the data point is
                #  still written as received.
                try:
                    self._run_experiment_post_processing(task)
                except Exception:
                    logger.exception(
                        "Experiment post-processing failed for job %s",
                        task.pre_processing_task.job.id,
                    )

                ExperimentDataRepository.write_experiment_data_by_job_id(
                    job_id=task.pre_processing_task.job.id,
                    data_point=task.data_point,
                )

            self._flush_finished_jobs()

    def _run_experiment_post_processing(self, task: PostProcessingTask) -> None:
        """Execute the experiment's optional post_processing for one data point.

        The experiment code runs through the experiment library client, isolated
        and checked out to the git revision that produced this data point (once
        per job, reused for the job's later data points -- see
        `_get_job_client`). Parameters the experiment updates are pushed to
        running jobs immediately via "calibration" events and uploaded to
        InfluxDB at most every `db_upload_interval`; `_flush_finished_jobs`
        performs a final upload when the job ends. Result channels updated by
        the experiment are merged into `task.data_point` so they end up in the
        stored data (the caller writes the data point after this method
        returns).
        """
        job = task.pre_processing_task.job
        state = self._job_states.setdefault(job.id, ExperimentPostProcessingState())

        if state.has_post_processing is False:
            return

        client = self._get_job_client(task, state)

        namespace = ExperimentIdentifier.from_str(job.experiment_source.experiment_id)

        # Same value source as sequence generation: the shared parameter dict,
        # overlaid with not-yet-uploaded post-processing updates and the scanned
        # values of this data point.
        parameter_dict: dict[str, DatabaseValueType] = {
            **ParametersRepository.get_shared_parameters(),
            **state.pending_parameters,
            **task.data_point.scan_params,
        }

        result = self._run_async(
            client.run_experiment_post_processing(
                exp_module_name=namespace.module_name,
                exp_instance_name=namespace.instance_name,
                parameter_dict=parameter_dict,
                result_channels=task.data_point.readouts.result_channels,
                post_processing_output=state.post_processing_output.values,
                shot_channels=task.data_point.readouts.shot_channels,
            )
        )

        state.has_post_processing = result["has_post_processing"]
        if not state.has_post_processing:
            return

        state.post_processing_output = PostProcessingOutput(
            values=result["post_processing_output"]
        )

        self._merge_result_channels(
            task=task,
            updated_result_channels=result["updated_result_channels"],
        )
        self._propagate_updated_parameters(
            job_id=job.id,
            state=state,
            updated_parameters=result["updated_parameters"],
            db_upload_interval=result["db_upload_interval"],
        )

    def _get_job_client(
        self, task: PostProcessingTask, state: ExperimentPostProcessingState
    ) -> ExperimentLibraryClient:
        """Get the client checked out to this job's revision, caching per job.

        Checking out a revision shells out to git, so it must happen once per
        job rather than once per data point -- data points from different
        concurrently-running jobs can interleave in the queue. Debug-mode jobs
        use the live (shared) client directly, matching the pre-processing
        worker; other jobs get an isolated copy so their checkout doesn't
        affect other jobs sharing `self._experiment_library_client`.
        """
        if state.client is not None:
            return state.client

        if task.pre_processing_task.debug_mode:
            client = self._experiment_library_client
        else:
            client = state.client_stack.enter_context(
                self._experiment_library_client.isolated()
            )
        client.checkout_revision(task.pre_processing_task.git_commit_hash)
        state.client = client
        return client

    @staticmethod
    def _merge_result_channels(
        task: PostProcessingTask,
        updated_result_channels: dict[str, float],
    ) -> None:
        """Merge result channels the experiment filled in into the data point.

        Only channels that the hardware already reported can be updated.
        """
        for channel_name, value in updated_result_channels.items():
            if channel_name in task.data_point.readouts.result_channels:
                task.data_point.readouts.result_channels[channel_name] = value
            else:
                logger.warning(
                    "Post-processing of job %s set unknown result channel %r; "
                    "ignoring it",
                    task.pre_processing_task.job.id,
                    channel_name,
                )

    def _propagate_updated_parameters(
        self,
        job_id: int,
        state: ExperimentPostProcessingState,
        updated_parameters: dict[str, DatabaseValueType],
        db_upload_interval: float | None,
    ) -> None:
        """Push updated parameters to running jobs and periodically to InfluxDB."""
        if not updated_parameters:
            return

        logger.debug(
            "Post-processing of job %s updated parameters %s",
            job_id,
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

        # db_upload_interval is in seconds.
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
                if state.client is not None:
                    self._run_async(state.client.aclose())
                state.client_stack.close()

    def _run_async(self, coroutine: Coroutine[Any, Any, T]) -> T:
        if self._loop is None:
            raise RuntimeError("Post-processing worker's event loop is not running")
        return self._loop.run_until_complete(coroutine)
