from datetime import datetime

import pydase

from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job, zurich_timezone
from icon.server.data_access.repositories.experiment_source_repository import (
    ExperimentSourceRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository

# from icon.server.api.models.scan_info import ScanInfo


class SchedulerController(pydase.DataService):
    def submit_job(
        self,
        *,
        # scan_info: ScanInfo,
        experiment_id: str,
        priority: int = 20,
        local_parameters_timestamp: datetime = datetime.now(tz=zurich_timezone),
        repetitions: int = 1,
        git_commit_hash: str | None = None,
    ) -> int:
        experiment_source = ExperimentSource(experiment_id=experiment_id)

        experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=experiment_source
        )
        job = Job(
            experiment_source=experiment_source,
            priority=priority,
            local_parameters_timestamp=local_parameters_timestamp,
            # scan_info=scan_info,
            repetitions=repetitions,
            git_commit_hash=git_commit_hash,
        )
        job = JobRepository.submit_job(job=job)

        return job.id
