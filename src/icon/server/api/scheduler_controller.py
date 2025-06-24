import logging
from datetime import datetime

import pydase

import icon.server.data_access.models.sqlite.scan_parameter as sqlite_scan_parameter
from icon.server.api.models.scan_parameter import ScanParameter
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job, timezone
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.experiment_source_repository import (
    ExperimentSourceRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository

logger = logging.getLogger(__name__)


class SchedulerController(pydase.DataService):
    def submit_job(  # noqa: PLR0913
        self,
        *,
        experiment_id: str,
        scan_parameters: list[ScanParameter],
        priority: int = 20,
        local_parameters_timestamp: datetime | None = None,
        repetitions: int = 1,
        number_of_shots: int = 50,
        git_commit_hash: str | None = None,
        auto_calibration: bool = False,
    ) -> int:
        if local_parameters_timestamp is None:
            local_parameters_timestamp = datetime.now(tz=timezone)

        experiment_source = ExperimentSource(experiment_id=experiment_id)

        experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=experiment_source
        )

        sqlite_scan_parameters = [
            sqlite_scan_parameter.ScanParameter(
                variable_id=param["id"],
                scan_values=param["values"],
                device_id=DeviceRepository.get_device_by_name(
                    name=param["device_name"]
                ).id
                if "device_name" in param
                else None,
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
            number_of_shots=number_of_shots,
            auto_calibration=auto_calibration,
            debug_mode=git_commit_hash is None,
        )
        job = JobRepository.submit_job(job=job)

        return job.id

    def get_scheduled_jobs(
        self,
        *,
        status: JobStatus | None = None,
        start: str | None = None,
        stop: str | None = None,
    ) -> dict[int, Job]:
        start_date = datetime.fromisoformat(start) if start is not None else None
        stop_date = datetime.fromisoformat(stop) if stop is not None else None

        return {
            job.id: job
            for job in JobRepository.get_jobs_by_status_and_timeframe(
                status=status, start=start_date, stop=stop_date
            )
        }
