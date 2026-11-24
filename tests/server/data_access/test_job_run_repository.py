from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
import pytz
import sqlalchemy
import sqlalchemy.orm

from icon.config import latest
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite import ExperimentSource, Job, JobRun
from icon.server.data_access.repositories import job_run_repository
from icon.server.data_access.repositories.job_run_repository import (
    JobRunRepository,
    ScheduledRun,
    scheduled_time_to_utc,
)

ZURICH = pytz.timezone("Europe/Zurich")


@pytest.fixture(autouse=True)
def _zurich_time_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    config = SimpleNamespace(date=latest.DateConfig(timezone="Europe/Zurich"))
    monkeypatch.setattr(job_run_repository, "get_config", lambda: config)


@pytest.mark.parametrize(
    ("scheduled_time", "expected"),
    [
        # Naive times are wall-clock times in the configured time zone.
        (datetime(2026, 3, 25, 0, 30), datetime(2026, 3, 24, 23, 30, tzinfo=UTC)),  # noqa: DTZ001
        (datetime(2026, 7, 1, 12, 0), datetime(2026, 7, 1, 10, 0, tzinfo=UTC)),  # noqa: DTZ001
        # Aware times keep their instant.
        (
            datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
            datetime(2026, 7, 1, 12, 0, tzinfo=UTC),
        ),
    ],
)
def test_scheduled_time_to_utc(scheduled_time: datetime, expected: datetime) -> None:
    utc = scheduled_time_to_utc(scheduled_time)

    assert utc == expected
    assert utc.tzinfo is UTC


def test_scheduled_runs_are_read_back_in_utc(
    database: sqlalchemy.engine.Engine,
) -> None:
    # Created like `now()` does; SQLite keeps only the Zurich wall-clock time.
    scheduled_time = ZURICH.localize(datetime(2026, 3, 25, 0, 30, 0, 123456))  # noqa: DTZ001
    with sqlalchemy.orm.Session(database) as session:
        source = ExperimentSource(experiment_id="mod.Ramsey (Ramsey)")
        session.add(source)
        session.flush()
        job = Job(experiment_source_id=source.id)
        session.add(job)
        session.flush()
        session.add(
            JobRun(
                job_id=job.id,
                scheduled_time=scheduled_time,
                status=JobRunStatus.DONE,
            )
        )
        session.commit()
        job_id = job.id

    expected = ScheduledRun(
        datetime(2026, 3, 24, 23, 30, 0, 123456, tzinfo=UTC), "mod.Ramsey (Ramsey)"
    )
    assert JobRunRepository.get_scheduled_run_by_job_id(job_id=job_id) == expected
    assert JobRunRepository.get_recent_scheduled_runs(limit=1) == [expected]
    assert JobRunRepository.get_scheduled_runs() == [expected]
