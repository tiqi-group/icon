from datetime import datetime

import pydase

import icon.server.data_access.models.sqlite.scan_parameter as sqlite_scan_parameter
from icon.server.api.models.scan_parameter import ScanParameter
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
        experiment_id: str,
        scan_parameters: list[ScanParameter],
        priority: int = 20,
        local_parameters_timestamp: datetime = datetime.now(tz=zurich_timezone),
        repetitions: int = 1,
        git_commit_hash: str | None = None,
        auto_calibration: bool = False,
    ) -> int:
        experiment_source = ExperimentSource(experiment_id=experiment_id)

        experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=experiment_source
        )
        sqlite_scan_parameters = [
            sqlite_scan_parameter.ScanParameter(
                variable_id=param["parameter"],
                scan_values=param["values"],
                # remote_source=param.remote_source,
            )
            for param in scan_parameters
        ]
        job = Job(
            experiment_source=experiment_source,
            priority=priority,
            local_parameters_timestamp=local_parameters_timestamp,
            scan_parameters=sqlite_scan_parameters,
            repetitions=repetitions,
            git_commit_hash=git_commit_hash,
        )
        job = JobRepository.submit_job(job=job)

        return job.id
