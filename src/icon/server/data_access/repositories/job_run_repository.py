import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy.orm
from sqlalchemy import select, update

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


def job_run_cancelled_or_failed(job_id: int) -> bool:
    """Check if a job's run was cancelled or failed.

    Args:
        job_id: ID of the job whose run should be checked.

    Returns:
        True if the run status is CANCELLED or FAILED, False otherwise.
    """

    job_run = JobRunRepository.get_run_by_job_id(job_id=job_id)
    if job_run.status in (JobRunStatus.CANCELLED, JobRunStatus.FAILED):
        logger.info(
            "JobRun with id %s %s.",
            job_run.id,
            job_run.status.value,
        )
        return True
    return False


class JobRunRepository:
    """Repository for `JobRun` entities.

    Provides methods to insert, update, and query job runs from the database.
    Emits Socket.IO events when job runs are created or updated.
    """

    @staticmethod
    def insert_run(*, run: JobRun) -> JobRun:
        """Insert a new job run and emit a creation event.

        Args:
            run: The job run instance to persist.

        Returns:
            The persisted job run with generated fields populated.
        """

        with sqlalchemy.orm.Session(engine) as session:
            session.add(run)
            session.commit()
            session.refresh(run)
            logger.debug("Created new run %s", run)

        emit_queue.put(
            {
                "event": "job_run.new",
                "data": {
                    "job_run": SQLAlchemyDictEncoder.encode(obj=run),
                },
            }
        )

        return run

    @staticmethod
    def update_run_by_id(
        *,
        run_id: int,
        status: JobRunStatus,
        log: str | None = None,
    ) -> JobRun:
        """Update a job run by ID and emit an update event.

        Args:
            run_id: The ID of the job run to update.
            status: New status of the run.
            log: Optional log message (e.g. failure reason).

        Returns:
            The updated job run.
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                update(JobRun)
                .where(JobRun.id == run_id)
                .values(status=status, log=log)
                .returning(JobRun)
            )
            run = session.execute(stmt).scalar_one()
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
            stmt = select(JobRun).where(JobRun.job_id == job_id)

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobRun.job))

            run = session.execute(stmt).scalar_one()
            logger.debug("Got JobRun by job_id %s", job_id)
        return run

    @staticmethod
    def get_scheduled_time_by_job_id(*, job_id: int) -> datetime:
        """Return the scheduled time of a run by job ID.

        Args:
            job_id: ID of the job.

        Returns:
            The scheduled start time of the run.
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobRun.scheduled_time).where(JobRun.job_id == job_id)

            scheduled_time = session.execute(stmt).scalar_one()
            logger.debug("Got scheduled time for job_id %s", job_id)
        return scheduled_time

    @staticmethod
    def set_parameter_update_timestamp(*, run_id: int, timestamp: datetime) -> None:
        """Set the paramter update timestamp.

        Args:
            job_id: ID of the job.
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
    def get_parameter_update_timestamp(*, run_id: int) -> datetime:
        """Get the paramter update timestamp.

        Args:
            job_id: ID of the job.
        Returns:
            The parameter update timestamp.
        """

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobRun.parameter_update_timestamp).where(JobRun.id == run_id)

            timestamp = session.execute(stmt).scalar_one()
            logger.debug("Got parameter update timestamp for run %s", run_id)

        return timestamp.replace(tzinfo=UTC)
