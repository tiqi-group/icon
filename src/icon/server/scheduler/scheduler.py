import multiprocessing
import time
from typing import Any

from icon.server.data_access.models.enums import JobIterationStatus, JobStatus
from icon.server.data_access.models.sqlite.job_iteration import JobIteration
from icon.server.data_access.repositories.job_iteration_repository import (
    JobIterationRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository


def initialise_job_table() -> None:
    # update job_iterations table
    job_iterations = JobIterationRepository.get_iterations_by_status(
        status=[JobIterationStatus.PENDING, JobIterationStatus.PROCESSING]
    )
    for job_iteration_ in job_iterations:
        JobIterationRepository.update_iteration(
            iteration=job_iteration_._tuple()[0],
            status=JobIterationStatus.CANCELLED,
            log="Cancelled when restarting scheduler.",
        )

    # update jobs table
    jobs = JobRepository.get_jobs_by_status(status=JobStatus.PROCESSING)
    for job_ in jobs:
        JobRepository.update_job_status(
            job=job_._tuple()[0], status=JobStatus.PROCESSED
        )


class Scheduler(multiprocessing.Process):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__()
        self.kwargs = kwargs

    def run(self) -> None:
        initialise_job_table()
        while True:
            jobs = JobRepository.get_jobs_by_status(status=JobStatus.SUBMITTED)
            for job_ in jobs:
                job = job_._tuple()[0]
                JobRepository.update_job_status(job=job, status=JobStatus.PROCESSING)
                iteration = JobIteration(
                    priority=job.priority,
                    job_id=job.id,
                )
                iteration = JobIterationRepository.insert_iteration(iteration=iteration)
            time.sleep(1)
