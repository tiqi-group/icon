import logging
import multiprocessing
import queue
import time
from datetime import datetime
from typing import Any

from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.job_run import (
    JobRun,
    timezone,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
)
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
        initialise_job_tables()
        while not self.exit_now.is_set():
            try:
                jobs = JobRepository.get_jobs_by_status_and_timeframe(
                    status=JobStatus.SUBMITTED
                )
                for job_ in jobs:
                    try:
                        job = JobRepository.update_job_status(
                            job=job_, status=JobStatus.PROCESSING
                        )
                        run = JobRun(
                            job_id=job.id, scheduled_time=datetime.now(tz=timezone)
                        )
                        run = JobRunRepository.insert_run(run=run)

                        self._pre_processing_queue.put(
                            PreProcessingTask(
                                job=job,
                                job_run=run,
                                git_commit_hash=job.git_commit_hash,
                                scan_parameters=job.scan_parameters,
                                local_parameters_timestamp=job.local_parameters_timestamp.astimezone(
                                    tz=timezone
                                ).isoformat(),
                                priority=job.priority,
                                auto_calibration=job.auto_calibration,
                                debug_mode=job.debug_mode,
                                repetitions=job.repetitions,
                            )
                        )
                    except Exception:
                        logger.exception(
                            "Failed to dispatch job %s, reverting to SUBMITTED",
                            job_.id,
                        )
                        try:
                            JobRepository.update_job_status(
                                job=job_, status=JobStatus.SUBMITTED
                            )
                        except Exception:
                            logger.exception(
                                "Failed to revert job %s back to SUBMITTED", job_.id
                            )
            except Exception:
                logger.exception("Unexpected error in scheduler loop")
            time.sleep(0.1)
