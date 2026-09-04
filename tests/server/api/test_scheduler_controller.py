from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pydase.units as u
import pytest

from icon.server.api.models.parameter_metadata import ParameterMetadata
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus


@pytest.fixture
def devices_controller() -> MagicMock:
    return MagicMock()


@pytest.fixture
def controller(devices_controller: MagicMock) -> SchedulerController:
    return SchedulerController(
        devices_controller=devices_controller,
        parameters_controller=MagicMock(),
    )


def _metadata(
    *,
    display_name: str = "",
    unit: str = "",
    default_value: float = 0,
    min_value: float | None = None,
    max_value: float | None = None,
    allowed_values: list[Any] | None = None,
) -> ParameterMetadata:
    return {
        "display_name": display_name,
        "unit": unit,
        "default_value": default_value,
        "min_value": min_value,
        "max_value": max_value,
        "allowed_values": allowed_values,
    }


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


def test_resolve_unit_from_parameter_metadata(controller: SchedulerController) -> None:
    controller._parameters_controller._all_parameter_metadata = {
        "tickle_frequency": _metadata(display_name="Tickle frequency", unit="MHz"),
        "empty_unit": _metadata(display_name="No unit", unit="  "),
    }

    assert controller._resolve_unit("tickle_frequency") == "MHz"
    assert controller._resolve_unit("empty_unit") is None
    assert controller._resolve_unit("unknown") is None


def test_resolve_unit_from_quantity_value(controller: SchedulerController) -> None:
    controller._parameters_controller._all_parameter_metadata = {}

    assert controller._resolve_unit("device.freq", value=u.Quantity(1, "MHz")) == "MHz"
    assert controller._resolve_unit("device.time", value=u.Quantity(1, "us")) == "µs"


@pytest.mark.asyncio
@patch("icon.server.api.scheduler_controller.ParametersRepository")
@patch("icon.server.api.scheduler_controller.ExperimentSourceRepository")
@patch("icon.server.api.scheduler_controller.JobRepository")
async def test_submit_job_persists_unit_from_metadata(
    mock_job_repo: MagicMock,
    mock_experiment_source_repo: MagicMock,
    mock_params_repo: MagicMock,
    controller: SchedulerController,
    devices_controller: MagicMock,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {
        "tickle_frequency": _metadata(display_name="Tickle frequency", unit="MHz"),
    }
    mock_params_repo.get_shared_parameter_by_id.return_value = 1.0
    mock_experiment_source_repo.get_or_create_experiment.return_value = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 7
    mock_job_repo.submit_job.return_value = mock_job

    job_id = await controller.submit_job(
        experiment_id="exp",
        scan_parameters=[{"id": "tickle_frequency", "values": [1.0, 2.0]}],
    )

    assert job_id == mock_job.id
    scan_parameter = mock_job_repo.submit_job.call_args.kwargs["job"].scan_parameters[0]
    assert scan_parameter.unit == "MHz"
    devices_controller.get_parameter_value.assert_not_called()


@pytest.mark.asyncio
@patch("icon.server.api.scheduler_controller.DeviceRepository")
@patch("icon.server.api.scheduler_controller.ExperimentSourceRepository")
@patch("icon.server.api.scheduler_controller.JobRepository")
async def test_submit_job_persists_unit_from_device_quantity(
    mock_job_repo: MagicMock,
    mock_experiment_source_repo: MagicMock,
    mock_device_repo: MagicMock,
    controller: SchedulerController,
    devices_controller: MagicMock,
) -> None:
    controller._parameters_controller._all_parameter_metadata = {}
    devices_controller.get_parameter_value = AsyncMock(
        return_value=u.Quantity(1, "MHz")
    )
    mock_device = MagicMock()
    mock_device.id = 3
    mock_device_repo.get_device_by_name.return_value = mock_device
    mock_experiment_source_repo.get_or_create_experiment.return_value = MagicMock()
    mock_job = MagicMock()
    mock_job.id = 8
    mock_job_repo.submit_job.return_value = mock_job

    job_id = await controller.submit_job(
        experiment_id="exp",
        scan_parameters=[
            {"id": "freq", "device_name": "RF", "values": [1.0, 2.0]},
        ],
    )

    assert job_id == mock_job.id
    scan_parameter = mock_job_repo.submit_job.call_args.kwargs["job"].scan_parameters[0]
    assert scan_parameter.unit == "MHz"
    devices_controller.get_parameter_value.assert_awaited_once_with(
        name="RF",
        parameter_id="freq",
    )
