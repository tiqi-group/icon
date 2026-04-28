from unittest.mock import MagicMock, patch

import pytest

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
    "run_status,should_update",
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
    "run_status,should_update",
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
    "run_status,should_cancel",
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
