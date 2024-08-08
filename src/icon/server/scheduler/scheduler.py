import multiprocessing
import queue
import time
from typing import Any

from icon.server.data_access.models.enums import JobIterationStatus, JobStatus
from icon.server.data_access.models.sqlite.job_iteration import JobIteration
from icon.server.data_access.repositories.job_iteration_repository import (
    JobIterationRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.pre_processing.task import PreProcessingTask


def initialise_job_table() -> None:
    # update job_iterations table
    job_iterations = JobIterationRepository.get_iterations_by_status(
        status=[JobIterationStatus.PENDING, JobIterationStatus.PROCESSING]
    )
    for job_iteration_ in job_iterations:
        JobIterationRepository.update_iteration(
            iteration=job_iteration_._tuple()[0],
            status=JobIterationStatus.CANCELLED,
            log="Cancelled during scheduler initialization.",
        )

    # update jobs table
    jobs = JobRepository.get_jobs_by_status(status=JobStatus.PROCESSING)
    for job_ in jobs:
        JobRepository.update_job_status(
            job=job_._tuple()[0], status=JobStatus.PROCESSED
        )


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
        initialise_job_table()
        while True:
            jobs = JobRepository.get_jobs_by_status(status=JobStatus.SUBMITTED)
            for job_ in jobs:
                job = JobRepository.update_job_status(
                    job=job_._tuple()[0], status=JobStatus.PROCESSING
                )
                iteration = JobIteration(
                    priority=job.priority,
                    job_id=job.id,
                )
                iteration = JobIterationRepository.insert_iteration(iteration=iteration)

                self._pre_processing_queue.put(
                    PreProcessingTask(
                        job_id=job.id,
                        iteration_id=iteration.id,
                        git_commit_hash=job.git_commit_hash,
                        local_parameters_timestamp=job.local_parameters_timestamp,
                        priority=job.priority,
                        experiment_file_path=job.experiment_source.file_path,
                        experiment_name=job.experiment_source.name,
                        auto_calibration=job.auto_calibration,
                    )
                )
            time.sleep(1)
