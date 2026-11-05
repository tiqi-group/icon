from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
import sqlalchemy
import sqlalchemy.orm

from icon.server.api.models.parameter_metadata import ParameterMetadata
from icon.server.api.models.scan_parameter import (
    DatabaseParameter,
    RealtimeParameter,
)
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite import (
    Job,
    JobRun,
)
from icon.server.pre_processing.arbiter import Arbiter, TaskQueue
from tests.server.conftest import SeedJob


@pytest.fixture
def task_arbiter() -> Arbiter:
    return Arbiter()


@pytest.fixture
def controller(task_arbiter: Arbiter) -> SchedulerController:
    return SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=MagicMock(),
        task_arbiter=task_arbiter,
    )


def _hands_over_the_runs_task(task_arbiter: Arbiter, run_id: int) -> bool:
    """Whether a task of the job run in the task queue would be handed over."""
    task_queue = TaskQueue(task_arbiter, 0, size=1)
    task_queue.put(
        cast(
            "Any",
            SimpleNamespace(
                priority=0,
                created=0,
                pre_processing_task=SimpleNamespace(job_run=SimpleNamespace(id=run_id)),
            ),
        )
    )
    handed_over = task_arbiter._next_worker() is not None
    task_queue.take_back(run_id)
    return handed_over


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
    task_arbiter: Arbiter,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSING, run_status=run_status)

    controller.pause_job(job_id=job_id)

    expected = JobRunStatus.PAUSED if should_update else run_status
    assert _run_status(database, run_id) == expected
    assert _hands_over_the_runs_task(task_arbiter, run_id) is not should_update


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
    task_arbiter: Arbiter,
    database: sqlalchemy.engine.Engine,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(job_status=JobStatus.PROCESSING, run_status=run_status)

    task_arbiter.hold(run_id)

    controller.resume_job(job_id=job_id)

    expected = JobRunStatus.PROCESSING if should_update else run_status
    assert _run_status(database, run_id) == expected
    assert _hands_over_the_runs_task(task_arbiter, run_id) is should_update


def test_paused_job_is_handed_over_again_on_resume(
    controller: SchedulerController,
    task_arbiter: Arbiter,
    seed_job: SeedJob,
) -> None:
    job_id, run_id = seed_job(
        job_status=JobStatus.PROCESSING, run_status=JobRunStatus.PROCESSING
    )

    controller.pause_job(job_id=job_id)
    assert not _hands_over_the_runs_task(task_arbiter, run_id)

    controller.resume_job(job_id=job_id)
    assert _hands_over_the_runs_task(task_arbiter, run_id)


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
