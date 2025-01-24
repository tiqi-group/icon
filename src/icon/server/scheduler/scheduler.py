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


def initialise_job_tables() -> None:
    # update job_runs table
    job_runs = JobRunRepository.get_runs_by_status(
        status=[JobRunStatus.PENDING, JobRunStatus.PROCESSING]
    )
    for job_run_ in job_runs:
        JobRunRepository.update_run_by_id(
            run_id=job_run_._tuple()[0].id,
            status=JobRunStatus.CANCELLED,
            log="Cancelled during scheduler initialization.",
        )

    # update jobs table
    jobs = JobRepository.get_jobs_by_status(status=JobStatus.PROCESSING)
    for job_ in jobs:
        JobRepository.update_job_status(
            job=job_._tuple()[0], status=JobStatus.PROCESSED
        )


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

    def run(self) -> None:
        initialise_job_tables()
        while not should_exit():
            jobs = JobRepository.get_jobs_by_status(status=JobStatus.SUBMITTED)
            for job_ in jobs:
                job = JobRepository.update_job_status(
                    job=job_._tuple()[0], status=JobStatus.PROCESSING
                )
                run = JobRun(job_id=job.id, scheduled_time=datetime.now(tz=timezone))
                run = JobRunRepository.insert_run(run=run)

                self._pre_processing_queue.put(
                    PreProcessingTask(
                        job_id=job.id,
                        job_run_id=run.id,
                        git_commit_hash=job.git_commit_hash,
                        local_parameters_timestamp=job.local_parameters_timestamp,
                        priority=job.priority,
                        experiment_id=job.experiment_source.experiment_id,
                        auto_calibration=job.auto_calibration,
                        debug_mode=job.debug_mode,
                        repetitions=job.repetitions,
                    )
                )
            time.sleep(1)
