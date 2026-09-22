from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import sqlalchemy
import sqlalchemy.orm

from icon.server.api.models.parameter_metadata import ParameterMetadata
from icon.server.api.models.scan_parameter import (
    DatabaseParameter,
    RealtimeParameter,
)
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus, ScanMode
from icon.server.data_access.models.sqlite import (
    Job,
    JobRun,
)
from tests.server.conftest import SeedJob


@pytest.fixture
def controller() -> SchedulerController:
    return SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=MagicMock(),
    )


def _run_status(engine: sqlalchemy.engine.Engine, run_id: int) -> JobRunStatus:
    with sqlalchemy.orm.Session(engine) as session:
        run = session.get(JobRun, run_id)
        assert run is not None
        return run.status


def _job_status(engine: sqlalchemy.engine.Engine, job_id: int) -> JobStatus:
    with sqlalchemy.orm.Session(engine) as session:
        job = session.get(Job, job_id)
        assert job is not None
        return job.status


@pytest.mark.parametrize(
    ("run_status", "should_update"),
    [
        (JobRunStatus.PROCESSING, True),
        (JobRunStatus.PENDING, False),
        (JobRunStatus.PAUSED, False),
        (JobRunStatus.DONE, False),
        (JobRunStatus.CANCELLED, False),
        (JobRunStatus.FAILED, False),
    ],
)
def test_pause_job_guards_by_status(
    run_status: JobRunStatus,
    *,
    should_update: bool,
    controller: SchedulerController,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSING, run_status=run_status)

    controller.pause_job(job_id=job_id)

    expected = JobRunStatus.PAUSED if should_update else run_status
    assert _run_status(database, run_id) == expected


@pytest.mark.parametrize(
    ("run_status", "should_update"),
    [
        (JobRunStatus.PAUSED, True),
        (JobRunStatus.PROCESSING, False),
        (JobRunStatus.PENDING, False),
        (JobRunStatus.DONE, False),
        (JobRunStatus.CANCELLED, False),
        (JobRunStatus.FAILED, False),
    ],
)
def test_resume_job_guards_by_status(
    run_status: JobRunStatus,
    *,
    should_update: bool,
    controller: SchedulerController,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSING, run_status=run_status)

    controller.resume_job(job_id=job_id)

    expected = JobRunStatus.PROCESSING if should_update else run_status
    assert _run_status(database, run_id) == expected


@pytest.mark.parametrize(
    ("run_status", "should_cancel"),
    [
        (JobRunStatus.PENDING, True),
        (JobRunStatus.PROCESSING, True),
        (JobRunStatus.PAUSED, True),
        (JobRunStatus.DONE, False),
        (JobRunStatus.CANCELLED, False),
        (JobRunStatus.FAILED, False),
    ],
)
def test_cancel_job_guards_by_run_status(
    run_status: JobRunStatus,
    *,
    should_cancel: bool,
    controller: SchedulerController,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSING, run_status=run_status)

    controller.cancel_job(job_id=job_id)

    expected = JobRunStatus.CANCELLED if should_cancel else run_status
    assert _run_status(database, run_id) == expected
    # The job itself is retired either way: it is no longer active.
    assert _job_status(database, job_id) == JobStatus.PROCESSED


@pytest.mark.parametrize(
    "job_status",
    [JobStatus.SUBMITTED, JobStatus.PROCESSING, JobStatus.PROCESSED],
)
def test_cancel_job_cancels_job_run(
    job_status: JobStatus,
    controller: SchedulerController,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=job_status, run_status=JobRunStatus.PROCESSING)

    controller.cancel_job(job_id=job_id)

    assert _run_status(database, run_id) == JobRunStatus.CANCELLED
    assert _job_status(database, job_id) == JobStatus.PROCESSED


def test_cancel_job_records_the_reason(
    controller: SchedulerController,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(
        job_status=JobStatus.PROCESSING, run_status=JobRunStatus.PROCESSING
    )

    controller.cancel_job(job_id=job_id)

    with sqlalchemy.orm.Session(database) as session:
        run = session.get(JobRun, run_id)
        assert run is not None
        assert run.log == "Cancelled through user interaction."


def _scan_parameter_spec(parameter_id: str, values: list[float]) -> dict[str, Any]:
    return {"id": parameter_id, "values": values}


@pytest.fixture
def submittable_controller() -> SchedulerController:
    """Controller whose parameter lookups resolve without hitting a database."""
    parameters_controller = MagicMock()
    parameters_controller._all_parameter_metadata = {}
    return SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=parameters_controller,
    )


@pytest.mark.asyncio
@patch("icon.server.api.scheduler_controller.ParametersRepository")
@patch("icon.server.api.scheduler_controller.ExperimentSourceRepository")
@patch("icon.server.api.scheduler_controller.JobRepository")
async def test_submit_job_rejects_correlated_scan_with_unequal_scan_values(
    mock_job_repo: MagicMock,
    mock_experiment_source_repo: MagicMock,  # noqa: ARG001
    mock_parameters_repo: MagicMock,
    submittable_controller: SchedulerController,
) -> None:
    """Mismatched correlated scans fail at submission, not on the queued job."""
    mock_parameters_repo.get_shared_parameter_by_id.return_value = 0.0

    with pytest.raises(ValueError, match="same number of scan values"):
        await submittable_controller.submit_job(
            experiment_id="experiment_library.experiments.exp.Class (Instance)",
            scan_parameters=[
                _scan_parameter_spec("a", [1.0, 2.0, 3.0]),
                _scan_parameter_spec("b", [10.0, 20.0]),
            ],
            scan_mode=ScanMode.CORRELATED,
        )

    mock_job_repo.submit_job.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("scan_mode", "expected"),
    [
        (ScanMode.CORRELATED, ScanMode.CORRELATED),
        # The frontend sends the mode as a plain string.
        ("correlated", ScanMode.CORRELATED),
        (ScanMode.MESH, ScanMode.MESH),
    ],
)
@patch("icon.server.api.scheduler_controller.ParametersRepository")
@patch("icon.server.api.scheduler_controller.ExperimentSourceRepository")
@patch("icon.server.api.scheduler_controller.JobRepository")
async def test_submit_job_persists_scan_mode(
    mock_job_repo: MagicMock,
    mock_experiment_source_repo: MagicMock,  # noqa: ARG001
    mock_parameters_repo: MagicMock,
    scan_mode: ScanMode | str,
    expected: ScanMode,
    submittable_controller: SchedulerController,
) -> None:
    mock_parameters_repo.get_shared_parameter_by_id.return_value = 0.0

    await submittable_controller.submit_job(
        experiment_id="experiment_library.experiments.exp.Class (Instance)",
        scan_parameters=[
            _scan_parameter_spec("a", [1.0, 2.0]),
            _scan_parameter_spec("b", [10.0, 20.0]),
        ],
        scan_mode=scan_mode,
    )

    assert mock_job_repo.submit_job.call_args.kwargs["job"].scan_mode == expected


@pytest.mark.asyncio
@patch("icon.server.api.scheduler_controller.ParametersRepository")
@patch("icon.server.api.scheduler_controller.ExperimentSourceRepository")
@patch("icon.server.api.scheduler_controller.JobRepository")
async def test_submit_job_defaults_to_mesh_scan(
    mock_job_repo: MagicMock,
    mock_experiment_source_repo: MagicMock,  # noqa: ARG001
    mock_parameters_repo: MagicMock,
    submittable_controller: SchedulerController,
) -> None:
    """Omitting scan_mode keeps the pre-existing mesh behaviour."""
    mock_parameters_repo.get_shared_parameter_by_id.return_value = 0.0

    await submittable_controller.submit_job(
        experiment_id="experiment_library.experiments.exp.Class (Instance)",
        scan_parameters=[
            _scan_parameter_spec("a", [1.0, 2.0, 3.0]),
            _scan_parameter_spec("b", [10.0, 20.0]),
        ],
    )

    assert mock_job_repo.submit_job.call_args.kwargs["job"].scan_mode == ScanMode.MESH


def _parameter_metadata(
    min_value: float | None, max_value: float | None
) -> ParameterMetadata:
    return {
        "display_name": "Wait Time",
        "unit": "us",
        "default_value": 1.0,
        "min_value": min_value,
        "max_value": max_value,
        "allowed_values": None,
    }


@pytest.mark.parametrize(
    ("min_value", "max_value", "values"),
    [
        (0.0, 100.0, [0.0, 50.0, 100.0]),
        (None, 100.0, [-1e9, 100.0]),
        (0.0, None, [0.0, 1e9]),
        (None, None, [-1e9, 1e9]),
        # Non-numeric values are not checked.
        (0.0, 100.0, [True, "a string"]),
    ],
)
def test_scan_values_within_bounds_are_accepted(
    min_value: float | None,
    max_value: float | None,
    values: list[Any],
    controller: SchedulerController,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {
        "wait_time": _parameter_metadata(min_value, max_value)
    }

    controller._check_scan_values_within_bounds(
        scan_parameters=[DatabaseParameter(id="wait_time", values=values)]
    )


@pytest.mark.parametrize(
    ("min_value", "max_value", "values"),
    [
        (0.0, 100.0, [-0.5, 50.0]),
        (0.0, 100.0, [50.0, 100.5]),
        (None, 100.0, [100.5]),
        (0.0, None, [-0.5]),
        (0.0, 100.0, [50, 120]),
    ],
)
def test_scan_values_outside_bounds_are_rejected(
    min_value: float | None,
    max_value: float | None,
    values: list[Any],
    controller: SchedulerController,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {
        "wait_time": _parameter_metadata(min_value, max_value)
    }

    with pytest.raises(ValueError, match="'Wait Time' is outside its bounds"):
        controller._check_scan_values_within_bounds(
            scan_parameters=[DatabaseParameter(id="wait_time", values=values)]
        )


def test_scan_values_without_metadata_are_not_checked(
    controller: SchedulerController,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {}

    controller._check_scan_values_within_bounds(
        scan_parameters=[
            DatabaseParameter(id="unknown_device_param", values=[-1e9, 1e9]),
            RealtimeParameter(n_scan_points=0),
        ]
    )
