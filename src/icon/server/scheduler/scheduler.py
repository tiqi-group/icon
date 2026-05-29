import logging
import multiprocessing
import queue
import time
from typing import Any

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.job_run import (
    timezone,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.data_access.repositories.job_transaction import JobTransaction
from icon.server.pre_processing.task import PreProcessingTask

logger = logging.getLogger(__name__)


def initialise_job_tables() -> None:
    # update job_runs table
    job_runs = JobRunRepository.get_runs_by_status(
        status=[JobRunStatus.PENDING, JobRunStatus.PROCESSING]
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
        JobRepository.update_job_status(job=job, status=JobStatus.PROCESSED)


class Scheduler(multiprocessing.Process):
    def __init__(
        self,
        pre_processing_queue: queue.PriorityQueue[PreProcessingTask],
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self.kwargs = kwargs
        self._pre_processing_queue = pre_processing_queue
        self.exit_now = multiprocessing.Event()

    def stop(self) -> None:
        self.exit_now.set()

    def run(self) -> None:
        self._initialize()
        while not self.exit_now.is_set():
            self._handle_submitted_jobs()
            time.sleep(0.1)

    def _initialize(self) -> None:
        initialise_job_tables()

    def _handle_submitted_jobs(self) -> None:
        try:
            jobs = JobRepository.get_jobs_by_status_and_timeframe(
                status=JobStatus.SUBMITTED
            )
        except Exception:
            logger.warning("Unable to retrieve submitted jobs from the database.")
            time.sleep(0.5)  # Delay before retry to avoid tight loop
            return

        for job_ in jobs:
            try:
                job, run = JobTransaction.insert_run_from_jobid(job_=job_)
            except Exception:
                logger.warning("Failed to create job run for job %s", job_.id)
                continue

            try:
                task = PreProcessingTask(
                    job=job,
                    job_run=run,
                    git_commit_hash=job.git_commit_hash,
                    scan_parameters=job.scan_parameters,
                    local_parameters_timestamp=job_.local_parameters_timestamp.astimezone(
                        tz=timezone
                    ).isoformat(),
                    priority=job.priority,
                    auto_calibration=job.auto_calibration,
                    debug_mode=job.debug_mode,
                    repetitions=job.repetitions,
                )

                self._pre_processing_queue.put(task)
            except Exception:
                logger.warning(
                    "Failed to enqueue pre-processing task for job %s", job_.id
                )
                # Failing to enqueue the task, marks the Job as PROCESSED and JobRun as FAILED as we don't want to create another JobRun.
                # The user should re-submit the job.
                JobRunRepository.update_run_by_id(
                    run_id=run.id,
                    status=JobRunStatus.FAILED,
                    log="Failed run due to failure to enqueue pre-processing task.",
                )
                JobRepository.update_job_status(job=job, status=JobStatus.PROCESSED)
