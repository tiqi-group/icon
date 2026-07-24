from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus, ScanMode


@pytest.fixture
def controller() -> SchedulerController:
    return SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=MagicMock(),
    )


def _mock_job_run(status: JobRunStatus, run_id: int = 42) -> MagicMock:
    run = MagicMock()
    run.id = run_id
    run.status = status
    return run


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
@patch("icon.server.api.scheduler_controller.JobRunRepository")
def test_pause_job_guards_by_status(
    mock_job_run_repo: MagicMock,
    run_status: JobRunStatus,
    *,
    should_update: bool,
    controller: SchedulerController,
) -> None:
    mock_job_run_repo.get_run_by_job_id.return_value = _mock_job_run(run_status)

    controller.pause_job(job_id=1)

    if should_update:
        mock_job_run_repo.update_run_by_id.assert_called_once_with(
            run_id=42,
            status=JobRunStatus.PAUSED,
            log="Paused through user interaction.",
        )
    else:
        mock_job_run_repo.update_run_by_id.assert_not_called()


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
@patch("icon.server.api.scheduler_controller.JobRunRepository")
def test_resume_job_guards_by_status(
    mock_job_run_repo: MagicMock,
    run_status: JobRunStatus,
    *,
    should_update: bool,
    controller: SchedulerController,
) -> None:
    mock_job_run_repo.get_run_by_job_id.return_value = _mock_job_run(run_status)

    controller.resume_job(job_id=1)

    if should_update:
        mock_job_run_repo.update_run_by_id.assert_called_once_with(
            run_id=42,
            status=JobRunStatus.PROCESSING,
        )
    else:
        mock_job_run_repo.update_run_by_id.assert_not_called()


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
@patch("icon.server.api.scheduler_controller.JobRepository")
@patch("icon.server.api.scheduler_controller.JobRunRepository")
def test_cancel_job_cancels_paused_runs(
    mock_job_run_repo: MagicMock,
    mock_job_repo: MagicMock,
    run_status: JobRunStatus,
    *,
    should_cancel: bool,
    controller: SchedulerController,
) -> None:
    mock_job = MagicMock()
    mock_job.status = JobStatus.PROCESSING
    mock_job_repo.get_job_by_id.return_value = mock_job
    mock_job_run_repo.get_run_by_job_id.return_value = _mock_job_run(run_status)

    controller.cancel_job(job_id=1)

    if should_cancel:
        mock_job_run_repo.update_run_by_id.assert_called_once_with(
            run_id=42,
            status=JobRunStatus.CANCELLED,
            log="Cancelled through user interaction.",
        )
    else:
        mock_job_run_repo.update_run_by_id.assert_not_called()


def _scan_parameter_spec(parameter_id: str, values: list[float]) -> dict[str, Any]:
    return {"id": parameter_id, "values": values}


@pytest.fixture
def submittable_controller() -> SchedulerController:
    """Controller whose parameter lookups resolve without hitting a database."""
    parameters_controller = MagicMock()
    parameters_controller._all_parameter_metadata = {}
    controller = SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=parameters_controller,
    )
    return controller


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
