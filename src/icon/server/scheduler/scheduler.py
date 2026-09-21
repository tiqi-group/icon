import logging
import multiprocessing
import queue
import time
from typing import Any

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.now import now
from icon.server.data_access.repositories import job_transactions
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
)
from icon.server.pre_processing.task import PreProcessingTask
from icon.server.utils.handle_keyboard_interrupt import handle_keyboard_interrupt

logger = logging.getLogger(__name__)


def initialise_job_tables() -> None:
    # update job_runs table
    job_runs = JobRunRepository.get_runs_by_status(
        status=[
            JobRunStatus.PENDING,
            JobRunStatus.PROCESSING,
            JobRunStatus.PAUSED,
        ]
    )
    for job_run in job_runs:
        JobRunRepository.update_run_by_id(
            run_id=job_run.id,
            status=JobRunStatus.CANCELLED,
            log="Cancelled during scheduler initialization.",
        )

    # update jobs table
    jobs = JobRepository.get_jobs_by_status_and_timeframe(status=JobStatus.PROCESSING)
    for job in jobs:
        logger.warning(
            "Job '%s' was left in PROCESSING state and is being marked as PROCESSED "
            "during scheduler initialization (likely abandoned due to a server restart).",
            job.id,
        )
        JobRepository.update_job_status(job_id=job.id, status=JobStatus.PROCESSED)


def should_exit() -> bool:
    return False


class Scheduler(multiprocessing.Process):
    def __init__(
        self,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.kwargs = kwargs
        self._pre_processing_queue = pre_processing_queue

    def _dispatch(self, job_: Job) -> None:
        dispatched = job_transactions.dispatch_job(job_id=job_.id)

        if dispatched is None:
            logger.info("Job %s not in SUBMITTED state. Skipping it.", job_.id)
            return

        job, run = dispatched

        try:
            self._pre_processing_queue.put(
                PreProcessingTask(
                    job=job,
                    job_run=run,
                    git_commit_hash=job.git_commit_hash,
                    scan_parameters=job.scan_parameters,
                    local_parameters_timestamp=job.local_parameters_timestamp.astimezone(
                        tz=now().tzinfo
                    ).isoformat(),
                    priority=job.priority,
                    auto_calibration=job.auto_calibration,
                    debug_mode=job.debug_mode,
                    repetitions=job.repetitions,
                )
            )
        except Exception:
            logger.exception("Failed to queue job %s, failing it", job_.id)
            job_transactions.fail_job(
                job_id=job_.id, log="Failed to queue the pre-processing task."
            )

    @handle_keyboard_interrupt(logger)
    def run(self) -> None:
        initialise_job_tables()
        while not should_exit():
            try:
                jobs = JobRepository.get_jobs_by_status_and_timeframe(
                    status=JobStatus.SUBMITTED
                )
                for job_ in jobs:
                    try:
                        self._dispatch(job_)
                    except Exception:
                        logger.exception("Failed to dispatch job %s", job_.id)
            except Exception:
                logger.exception("Unexpected error in scheduler loop")
            time.sleep(0.1)
