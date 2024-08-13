from datetime import datetime

import pydase

from icon.server.api.models.experiment import Experiment
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
        experiment: Experiment,
        # scan_info: ScanInfo,
        priority: int = 20,
        local_parameters_timestamp: datetime = datetime.now(tz=zurich_timezone),
    ) -> int:
        experiment_source = ExperimentSource(
            name=experiment.name, file_path=str(experiment.file_path)
        )

        experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=experiment_source
        )
        job = Job(
            experiment_source=experiment_source,
            priority=priority,
            local_parameters_timestamp=local_parameters_timestamp,
            # scan_info=scan_info,
        )
        job = JobRepository.submit_job(job=job)

        return job.id
