import logging
from datetime import datetime
from typing import Any

import pydase

import icon.server.data_access.models.sqlite.scan_parameter as sqlite_scan_parameter
from icon.server.api.devices_controller import DevicesController
from icon.server.api.models.scan_parameter import ScanParameter
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job, timezone
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.repositories.device_repository import DeviceRepository
from icon.server.data_access.repositories.experiment_source_repository import (
    ExperimentSourceRepository,
)
from icon.server.data_access.repositories.job_repository import JobRepository
from icon.server.data_access.repositories.job_run_repository import JobRunRepository
from icon.server.data_access.repositories.parameters_repository import (
    ParametersRepository,
)

logger = logging.getLogger(__name__)


class SchedulerController(pydase.DataService):
    def __init__(self, devices_controller: DevicesController) -> None:
        super().__init__()
        self.__devices_controller = devices_controller

    async def submit_job(  # noqa: PLR0913
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
        sqlite_scan_parameters = []

        for param in scan_parameters:
            scan_values = await self.__cast_scan_values_to_param_type(
                scan_parameter=param
            )

            if len(scan_values) == 0:
                raise RuntimeError(f"Scan value of {param['id']} are empty")

            sqlite_scan_parameters.append(
                sqlite_scan_parameter.ScanParameter(
                    variable_id=param["id"],
                    scan_values=scan_values,
                    device_id=DeviceRepository.get_device_by_name(
                        name=param["device_name"]
                    ).id
                    if "device_name" in param
                    else None,
                )
            )
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

    def cancel_job(self, *, job_id: int) -> None:
        job = JobRepository.get_job_by_id(job_id=job_id)
        if job.status in (JobStatus.PROCESSING, JobStatus.SUBMITTED):
            JobRepository.update_job_status(job=job, status=JobStatus.PROCESSED)
            job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
            if job_run.status in (JobRunStatus.PENDING, JobRunStatus.PROCESSING):
                JobRunRepository.update_run_by_id(
                    run_id=job_run.id,
                    status=JobRunStatus.CANCELLED,
                    log="Cancelled through user interaction.",
                )

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

    def get_job_by_id(self, *, job_id: int) -> Job:
        return JobRepository.get_job_by_id(job_id=job_id, load_experiment_source=True)

    def get_job_run_by_id(self, *, job_id: int) -> JobRun:
        return JobRunRepository.get_run_by_job_id(job_id=job_id)

    async def __cast_scan_values_to_param_type(
        self,
        scan_parameter: ScanParameter,
    ) -> list[Any]:
        scan_values = scan_parameter["values"]
        parameter_id = scan_parameter["id"]

        if "device_name" in scan_parameter:
            current_value = await self.__devices_controller.get_parameter_value(
                name=scan_parameter["device_name"],
                parameter_id=parameter_id,
            )

        else:
            current_value = ParametersRepository.get_shared_parameter_by_id(
                parameter_id=parameter_id
            )
            if current_value is None:
                return scan_values

        current_type = type(current_value)
        return [current_type(value) for value in scan_values]
