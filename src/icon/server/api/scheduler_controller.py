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


class SchedulerController(pydase.DataService):
    """Controller to submit, inspect, and cancel scheduled jobs.

    Provides methods to submit new jobs, cancel pending or running jobs, and query jobs
    or runs by ID or status. Ensures scan parameters are cast to the correct runtime
    type before persisting them.
    """

    def __init__(self, devices_controller: DevicesController) -> None:
        """
        Args:
            devices_controller: Reference to the devices controller. Used to read
                current values of device parameters when casting scan values.
        """

        super().__init__()
        self._devices_controller = devices_controller

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
        """Create and submit a job with typed scan parameters.

        Each scan parameter's values are cast to the current type of the target
        parameter (device parameter via `DevicesController` or shared parameter via
        `ParametersRepository`).

        Args:
            experiment_id: Experiment identifier (from experiment library).
            scan_parameters: List of scan parameter specs (id, values, optional
                device_name).
            priority: Higher values run sooner.
            local_parameters_timestamp: ISO timestamp to snapshot local parameters;
                defaults to `datetime.now(tz=timezone)`.
            repetitions: Number of experiment repetitions.
            number_of_shots: Shots per data point.
            git_commit_hash: Git commit to associate with the job; if `None`, job is
                marked `debug_mode=True`.
            auto_calibration: Whether to run auto-calibration for the job.

        Returns:
            The persisted job ID.
        """

        if local_parameters_timestamp is None:
            local_parameters_timestamp = datetime.now(tz=timezone)

        experiment_source = ExperimentSource(experiment_id=experiment_id)

        experiment_source = ExperimentSourceRepository.get_or_create_experiment(
            experiment_source=experiment_source
        )
        sqlite_scan_parameters = []

        for param in scan_parameters:
            scan_values = await self._cast_scan_values_to_param_type(
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
        """Cancel a queued or running job.

        The following status updates are performed:

        - Job: PROCESSING/SUBMITTED → PROCESSED
        - JobRun: PENDING/PROCESSING → CANCELLED

        Args:
            job_id: ID of the job to cancel.
        """

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
        """List jobs filtered by status and optional ISO timeframe.

        Args:
            status: Optional job status filter.
            start: Optional ISO8601 start timestamp (inclusive).
            stop: Optional ISO8601 stop timestamp (exclusive).

        Returns:
            Mapping from job ID to job record.
        """

        start_date = datetime.fromisoformat(start) if start is not None else None
        stop_date = datetime.fromisoformat(stop) if stop is not None else None

        return {
            job.id: job
            for job in JobRepository.get_jobs_by_status_and_timeframe(
                status=status, start=start_date, stop=stop_date
            )
        }

    def get_job_by_id(self, *, job_id: int) -> Job:
        """Fetch a job with its experiment source and scan parameters.

        Args:
            job_id: Job identifier.

        Returns:
            The job record.
        """

        return JobRepository.get_job_by_id(
            job_id=job_id, load_experiment_source=True, load_scan_parameters=True
        )

    def get_job_run_by_id(self, *, job_id: int) -> JobRun:
        """Fetch the run record for a given job.

        Args:
            job_id: Job identifier.

        Returns:
            The associated run record.
        """

        return JobRunRepository.get_run_by_job_id(job_id=job_id)

    async def _cast_scan_values_to_param_type(
        self,
        scan_parameter: ScanParameter,
    ) -> list[Any]:
        """Cast scan values to the current parameter's runtime type.

        If `device_name` is present, the current value is read from the device
        via `DevicesController`. Otherwise, the shared parameter value is read
        from `ParametersRepository`. If no current value is found, the original
        values are returned unchanged.

        Args:
            scan_parameter: Scan parameter spec with `id`, `values`, and optional
                `device_name`.

        Returns:
            Values cast to `type(current_value)` when available, otherwise the original
                values.
        """
        scan_values = scan_parameter["values"]
        parameter_id = scan_parameter["id"]

        if "device_name" in scan_parameter:
            current_value = await self._devices_controller.get_parameter_value(
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
