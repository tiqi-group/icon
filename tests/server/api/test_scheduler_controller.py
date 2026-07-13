from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from icon.server.api.models.parameter_metadata import ParameterMetadata
from icon.server.api.models.scan_parameter import (
    DatabaseParameter,
    RealtimeParameter,
    ScanParameter,
)
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus


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
    ("min_value", "max_value", "values", "expected"),
    [
        (0.0, 100.0, [0.0, 50.0, 100.0], [0.0, 50.0, 100.0]),
        (0.0, 100.0, [-0.5, 50.0], [0.0, 50.0]),
        (0.0, 100.0, [50.0, 100.5], [50.0, 100.0]),
        (0.0, 100.0, [-20.0, 50.0, 120.0], [0.0, 50.0, 100.0]),
        (None, 100.0, [-1e9, 100.5], [-1e9, 100.0]),
        (0.0, None, [-0.5, 1e9], [0.0, 1e9]),
        (None, None, [-1e9, 1e9], [-1e9, 1e9]),
        # Non-numeric values are left untouched.
        (0.0, 100.0, [True, "a string"], [True, "a string"]),
        # Clamping preserves the value's type (int stays int).
        (0.0, 100.0, [-5, 50, 120], [0, 50, 100]),
    ],
)
def test_clamp_scan_values_to_bounds(
    min_value: float | None,
    max_value: float | None,
    values: list[Any],
    expected: list[Any],
    controller: SchedulerController,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {
        "wait_time": _parameter_metadata(min_value, max_value)
    }
    param = DatabaseParameter(id="wait_time", values=values)
    scan_parameters: list[ScanParameter] = [param]

    controller._clamp_scan_values_to_bounds(scan_parameters=scan_parameters)

    assert param.values == expected
    assert [type(value) for value in param.values] == [
        type(value) for value in expected
    ]


def test_clamp_scan_values_without_metadata_leaves_values_untouched(
    controller: SchedulerController,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {}
    param = DatabaseParameter(id="unknown_device_param", values=[-1e9, 1e9])

    controller._clamp_scan_values_to_bounds(
        scan_parameters=[param, RealtimeParameter(n_scan_points=0)]
    )

    assert param.values == [-1e9, 1e9]
