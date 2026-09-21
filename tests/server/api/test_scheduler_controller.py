from unittest.mock import MagicMock

import pytest
import sqlalchemy
import sqlalchemy.orm

from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
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
