import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NamedTuple

import sqlalchemy.orm
from sqlalchemy import Select, select, update
from sqlalchemy.exc import NoResultFound

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class ScheduledRun(NamedTuple):
    """What a run's result file is named after."""

    scheduled_time: datetime
    experiment_id: str


def _select_scheduled_runs() -> Select[tuple[datetime, str]]:
    return (
        select(JobRun.scheduled_time, ExperimentSource.experiment_id)
        .join(JobRun.job)
        .join(Job.experiment_source)
    )


def run_cancelled_or_failed(job_run: JobRun) -> bool:
    """Check if an already fetched run was cancelled or failed.

    Args:
        job_run: The run to check.

    Returns:
        True if the run status is CANCELLED or FAILED, False otherwise.
    """
    if job_run.status in (JobRunStatus.CANCELLED, JobRunStatus.FAILED):
        logger.info(
            "JobRun with id %s %s.",
            job_run.id,
            job_run.status.value,
        )
        return True
    return False


def job_run_cancelled_or_failed(job_id: int) -> bool:
    """Check if a job's run was cancelled or failed.

    Args:
        job_id: ID of the job whose run should be checked.

    Returns:
        True if the run status is CANCELLED or FAILED, False otherwise.
    """
    return run_cancelled_or_failed(JobRunRepository.get_run_by_job_id(job_id=job_id))


class JobRunRepository:
    """Repository for `JobRun` entities.

    Provides methods to update and query job runs from the database. Runs are
    created by `job_transactions.dispatch_job`.
    Emits Socket.IO events when job runs are updated.
    """

    @staticmethod
    def update_run_by_id(
        *,
        run_id: int,
        status: JobRunStatus,
        log: str | None = None,
        only_if_status: Sequence[JobRunStatus] | None = None,
    ) -> JobRun | None:
        """Update a job run by ID and emit an update event.

        Args:
            run_id: The ID of the job run to update.
            status: New status of the run.
            log: Optional log message (e.g. failure reason).
            only_if_status: Apply the update only if current status is in the list.

        Returns:
            The updated job run, or None when the current status is non of the
            `only_if_status` statuses.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = update(JobRun).where(JobRun.id == run_id)
            if only_if_status is not None:
                stmt = stmt.where(JobRun.status.in_(only_if_status))

            run = session.execute(
                stmt.values(status=status, log=log).returning(JobRun)
            ).scalar_one_or_none()

            if run is None:
                if only_if_status is None:
                    raise NoResultFound(f"No job run with id {run_id}")
                return None

            session.commit()

            logger.debug("Updated run %s", run)

        emit_queue.put(
            {
                "event": "job_run.update",
                "data": {
                    "run_id": run_id,
                    "updated_properties": {
                        "status": status.value,
                        "log": log,
                    },
                },
            }
        )

        return run

    @staticmethod
    def get_runs_by_status(
        *,
        status: JobRunStatus | list[JobRunStatus],
        load_job: bool = False,
    ) -> Sequence[JobRun]:
        """Return job runs filtered by status.

        Args:
            status: Single or list of run statuses to filter on.
            load_job: If True, eagerly load the related `Job`.

        Returns:
            All matching runs.
        """
        if not isinstance(status, list):
            status = [status]

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(JobRun)
                .where(JobRun.status.in_(status))
                .order_by(JobRun.scheduled_time.asc())
            )

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobRun.job))

            return session.execute(stmt).scalars().all()

    @staticmethod
    def get_run_by_job_id(*, job_id: int, load_job: bool = False) -> JobRun:
        """Return the run associated with a given job ID.

        Args:
            job_id: ID of the job.
            load_job: If True, eagerly load the related `Job`.

        Returns:
            The run linked to the given job.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(JobRun)
                .where(JobRun.job_id == job_id)
                .order_by(JobRun.scheduled_time.desc())
                .limit(1)
            )

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobRun.job))

            run = session.execute(stmt).scalar_one()
            logger.debug("Got JobRun by job_id %s", job_id)
        return run

    @staticmethod
    def get_scheduled_run_by_job_id(*, job_id: int) -> ScheduledRun:
        """Return the scheduled time and experiment of a run by job ID.

        Args:
            job_id: ID of the job.

        Returns:
            The scheduled start time and experiment ID of the run.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                _select_scheduled_runs()
                .where(JobRun.job_id == job_id)
                .order_by(JobRun.scheduled_time.desc())
                .limit(1)
            )

            run = ScheduledRun(*session.execute(stmt).one())
            logger.debug("Got scheduled run for job_id %s", job_id)
        return run

    @staticmethod
    def get_recent_scheduled_runs(*, limit: int) -> list[ScheduledRun]:
        """Return the scheduled time and experiment of the most recent runs.

        Args:
            limit: Maximum number of runs to return.

        Returns:
            Runs ordered from newest to oldest.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                _select_scheduled_runs()
                .where(JobRun.status != JobRunStatus.PENDING)
                .order_by(JobRun.scheduled_time.desc())
                .limit(limit)
            )

            runs = [ScheduledRun(*row) for row in session.execute(stmt)]
            logger.debug("Got the %s most recent scheduled runs", limit)
        return runs

    @staticmethod
    def get_scheduled_runs() -> list[ScheduledRun]:
        """Return the scheduled time and experiment of every run."""
        with sqlalchemy.orm.Session(engine) as session:
            return [
                ScheduledRun(*row) for row in session.execute(_select_scheduled_runs())
            ]

    @staticmethod
    def set_parameter_update_timestamp(*, run_id: int, timestamp: datetime) -> None:
        """Set the paramter update timestamp.

        Args:
            run_id: ID of the job.
            timestamp: New parameter update timestamp.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                update(JobRun)
                .where(JobRun.id == run_id)
                .values(parameter_update_timestamp=timestamp.astimezone(UTC))
                .returning(JobRun)
            )

            run = session.execute(stmt).scalar_one()
            session.commit()

            logger.debug("Updated parameter update timestam for run %s", run)

    @staticmethod
    def get_parameter_update_timestamp(*, run_id: int) -> datetime | None:
        """Get the paramter update timestamp.

        Args:
            run_id: ID of the job.

        Returns:
            The parameter update timestamp, or None if no parameter update has
            been recorded for this run yet.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobRun.parameter_update_timestamp).where(JobRun.id == run_id)

            timestamp = session.execute(stmt).scalar_one()
            logger.debug("Got parameter update timestamp for run %s", run_id)

        if timestamp is None:
            return None
        return timestamp.replace(tzinfo=UTC)


def try_update_run_by_id(
    *,
    run_id: int,
    status: JobRunStatus,
    log: str | None = None,
    only_if_status: Sequence[JobRunStatus] | None = None,
) -> JobRun | None:
    """Update a job run, logging any failure instead of raising.

    Args:
        run_id: ID of the job run to update.
        status: New status of the run.
        log: Optional log message (e.g. failure reason).
        only_if_status: Apply the update only while the stored status is one of
            these; see `JobRunRepository.update_run_by_id`.

    Returns:
        The updated job run, or None when the update failed or did not apply.
    """
    try:
        return JobRunRepository.update_run_by_id(
            run_id=run_id, status=status, log=log, only_if_status=only_if_status
        )
    except Exception:
        logger.exception(
            "Failed to update run '%s' to status '%s'", run_id, status.value
        )
        return None
