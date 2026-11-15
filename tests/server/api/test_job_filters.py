"""Filtered listings remain complete across page limits and calendar boundaries."""

# SQLite stores naive ICON-local wall times, including on DST transition days.
# ruff: noqa: DTZ001

from datetime import datetime
from typing import TypedDict
from unittest.mock import MagicMock

import pytest
import sqlalchemy
import sqlalchemy.orm

from icon.server.api.job_filters import job_date_bounds
from icon.server.api.scheduler_controller import SchedulerController
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite import ExperimentSource, Job


class JobFilters(TypedDict, total=False):
    experiment_ids: list[str]
    created_from: str
    created_to: str


def add_job(
    session: sqlalchemy.orm.Session,
    experiment: str,
    created: datetime,
    status: JobStatus = JobStatus.PROCESSED,
) -> int:
    source = ExperimentSource(experiment_id=experiment)
    job = Job(experiment_source=source, status=status)
    session.add(job)
    session.flush()
    session.execute(
        sqlalchemy.update(Job).where(Job.id == job.id).values(created=created)
    )
    return job.id


@pytest.fixture
def controller() -> SchedulerController:
    return SchedulerController(
        devices_controller=MagicMock(),
        parameters_controller=MagicMock(),
    )


def test_filters_apply_before_pagination(
    database: sqlalchemy.engine.Engine,
    controller: SchedulerController,
) -> None:
    with sqlalchemy.orm.Session(database) as session:
        matching = [
            add_job(session, "archived.Scan", datetime(2026, 10, 25, 12))
            for _ in range(105)
        ]
        for _ in range(110):
            add_job(session, "other.Scan", datetime(2026, 11, 5, 12))
        session.commit()
    filters: JobFilters = {
        "experiment_ids": ["archived.Scan"],
        "created_from": "2026-10-25",
        "created_to": "2026-10-25",
    }
    first = controller.get_job_list(**filters)
    second = controller.get_job_list(**filters, before_id=first[-1]["id"])
    assert [row["id"] for row in first + second] == list(reversed(matching))
    assert len(first) == 100  # noqa: PLR2004
    assert (
        controller.get_job_list(**filters, job_id=matching[0])[0]["id"] == matching[0]
    )
    assert controller.get_job_list(**filters, job_id=matching[-1] + 1) == []
    assert controller.get_job_list()[0]["experiment_id"] == "other.Scan"
    assert controller.get_job_filter_options()["experiment_ids"] == [
        "archived.Scan",
        "other.Scan",
    ]


def test_calendar_boundaries_and_active_jobs_use_the_same_filters(
    database: sqlalchemy.engine.Engine,
    controller: SchedulerController,
) -> None:
    with sqlalchemy.orm.Session(database) as session:
        before = add_job(session, "test.Scan", datetime(2026, 10, 24, 23, 59, 59))
        first = add_job(session, "test.Scan", datetime(2026, 10, 25))
        last = add_job(session, "test.Scan", datetime(2026, 10, 25, 23, 59, 59, 999999))
        after = add_job(session, "test.Scan", datetime(2026, 10, 26))
        active = add_job(
            session, "test.Scan", datetime(2026, 10, 25, 12), JobStatus.PROCESSING
        )
        add_job(session, "other.Scan", datetime(2026, 10, 25, 12), JobStatus.SUBMITTED)
        session.commit()
    filters: JobFilters = {
        "experiment_ids": ["test.Scan"],
        "created_from": "2026-10-25",
        "created_to": "2026-10-25",
    }
    assert [row["id"] for row in controller.get_job_list(**filters)] == [last, first]
    assert [row["id"] for row in controller.get_active_jobs(**filters)] == [active]
    assert controller.get_active_jobs(**filters, job_id=before) == []
    assert [
        row["id"] for row in controller.get_job_list(created_from="2026-10-26")
    ] == [after]


@pytest.mark.parametrize(
    ("start", "stop"),
    [
        ("2026-02-30", None),
        (None, "not-a-date"),
        ("2026-11-05", "2026-11-04"),
        (None, "9999-12-31"),
    ],
)
def test_invalid_date_bounds(start: str | None, stop: str | None) -> None:
    with pytest.raises(
        ValueError,
        match=r"day is out of range|Invalid isoformat|From date|Through date",
    ):
        job_date_bounds(start, stop)


def test_multiple_experiments_share_one_pagination_cursor(
    database: sqlalchemy.engine.Engine,
    controller: SchedulerController,
) -> None:
    with sqlalchemy.orm.Session(database) as session:
        expected = []
        for index in range(130):
            experiment = "scan.A" if index % 2 else "scan.B"
            expected.append(add_job(session, experiment, datetime(2026, 11, 5, 12)))
            add_job(session, "unselected.Scan", datetime(2026, 11, 5, 12))
        session.commit()
    filters: JobFilters = {"experiment_ids": ["scan.A", "scan.B", "scan.A"]}
    first = controller.get_job_list(**filters)
    second = controller.get_job_list(**filters, before_id=first[-1]["id"])
    assert [row["id"] for row in first + second] == list(reversed(expected))
    assert len(first) == 100  # noqa: PLR2004
    assert len(second) == 30  # noqa: PLR2004


def test_all_none_and_exact_experiment_identity(
    database: sqlalchemy.engine.Engine,
    controller: SchedulerController,
) -> None:
    with sqlalchemy.orm.Session(database) as session:
        first = add_job(session, "Scan (instance A)", datetime(2026, 11, 5, 12))
        second = add_job(session, "Scan (instance B)", datetime(2026, 11, 5, 12))
        active = add_job(
            session,
            "Scan (instance A)",
            datetime(2026, 11, 5, 12),
            JobStatus.SUBMITTED,
        )
        session.commit()
    assert [row["id"] for row in controller.get_job_list()] == [second, first]
    assert controller.get_job_list(experiment_ids=[]) == []
    assert controller.get_active_jobs(experiment_ids=[]) == []
    assert controller.get_job_list(experiment_ids=["missing.Scan"]) == []
    assert [
        row["id"]
        for row in controller.get_job_list(
            experiment_ids=["Scan (instance A)"],
        )
    ] == [first]
    assert [
        row["id"]
        for row in controller.get_active_jobs(
            experiment_ids=["Scan (instance A)"],
        )
    ] == [active]
    assert (
        controller.get_job_list(
            experiment_ids=["Scan (instance A)"],
            job_id=second,
        )
        == []
    )
