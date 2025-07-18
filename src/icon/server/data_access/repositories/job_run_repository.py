import logging
from collections.abc import Sequence
from datetime import datetime

import sqlalchemy.orm
from sqlalchemy import select, update

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


def job_run_cancelled_or_failed(job_id: int) -> bool:
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
    @staticmethod
    def insert_run(
        *,
        run: JobRun,
    ) -> JobRun:
        """Creates a new JobRun instance in the database and returns this
        instance.
        """

        with sqlalchemy.orm.Session(engine) as session:
            session.add(run)
            session.commit()
            session.refresh(run)  # Refresh to get the ID
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
        """Updates a JobRun instance in the database and returns this instance."""

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
        """Gets all the JobRun instances with given status."""

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
    def get_run_by_job_id(
        *,
        job_id: int,
        load_job: bool = False,
    ) -> JobRun:
        """Gets the JobRun instances with given job_id."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobRun).where(JobRun.job_id == job_id)

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobRun.job))

            run = session.execute(stmt).scalar_one()
            logger.debug("Got JobRun by job_id %s", job_id)
        return run

    @staticmethod
    def get_scheduled_time_by_job_id(
        *,
        job_id: int,
    ) -> datetime:
        """Gets the scheduled time of the run with given job_id."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobRun.scheduled_time).where(JobRun.job_id == job_id)

            scheduled_time = session.execute(stmt).scalar_one()
            logger.debug("Got scheduled time for job_id %s", job_id)
        return scheduled_time
