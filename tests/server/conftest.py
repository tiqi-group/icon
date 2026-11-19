"""Fixtures for the server tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Protocol
from unittest.mock import MagicMock

import pytest
import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.db_context.sqlite.engine import CachedEngine
from icon.server.data_access.models.sqlite import (
    Base,
    ExperimentSource,
    Job,
    JobRun,
)
from icon.server.data_access.repositories import (
    device_repository,
    experiment_source_repository,
    job_repository,
    job_run_repository,
    job_transactions,
)

if TYPE_CHECKING:
    from icon.server.data_access.models.enums import JobRunStatus, JobStatus

_REPOSITORY_MODULES = (
    device_repository,
    experiment_source_repository,
    job_repository,
    job_run_repository,
    job_transactions,
)


class InMemoryCachedEngine(CachedEngine):
    """A `CachedEngine` backed by a shared in-memory SQLite database.

    The path is never read from or written to; `get_cached` returns the one
    in-memory engine for any path.
    """

    def __init__(self) -> None:
        # Only the identity the base class keeps; never read from or written to.
        self.path = Path("icon.sqlite")
        self._engine = sqlalchemy.create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=sqlalchemy.pool.StaticPool,
        )

    def get_cached(self, path: str | Path) -> sqlalchemy.engine.Engine:  # noqa: ARG002
        # The path is ignored; every caller gets the one in-memory engine.
        return self._engine


@pytest.fixture
def engine_cache() -> CachedEngine:
    """A throwaway in-memory `CachedEngine`."""
    return InMemoryCachedEngine()


@pytest.fixture
def database(
    monkeypatch: pytest.MonkeyPatch, engine_cache: CachedEngine
) -> sqlalchemy.engine.Engine:
    """A throwaway SQLite database wired into the repository modules.

    Returns:
        The engine, for seeding rows and asserting on stored state.
    """
    engine = engine_cache.get_cached(engine_cache.path)
    Base.metadata.create_all(engine)
    for module in _REPOSITORY_MODULES:
        # Not every repository emits events.
        monkeypatch.setattr(module, "emit_queue", MagicMock(), raising=False)
    return engine


class SeedJob(Protocol):
    def __call__(
        self, *, job_status: JobStatus, run_status: JobRunStatus
    ) -> tuple[int, int]: ...


@pytest.fixture
def seed_job(database: sqlalchemy.engine.Engine) -> SeedJob:
    """Return a factory that stores one job and its run, returning their IDs."""

    def _seed(*, job_status: JobStatus, run_status: JobRunStatus) -> tuple[int, int]:
        with sqlalchemy.orm.Session(database) as session:
            source = ExperimentSource(experiment_id="test.MockExperiment")
            session.add(source)
            session.flush()

            job = Job(
                experiment_source_id=source.id,
                status=job_status,
                created=datetime.now(UTC),
            )
            session.add(job)
            session.flush()

            run = JobRun(job_id=job.id, status=run_status)
            session.add(run)
            session.commit()
            return job.id, run.id

    return _seed
