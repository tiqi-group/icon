import logging
from collections.abc import Sequence
from typing import cast

import sqlalchemy.orm
from sqlalchemy import select

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.job import Job

logger = logging.getLogger(__name__)


class JobRepository:
    @staticmethod
    def submit_job(
        *,
        job: Job,
    ) -> Job:
        """Creates a new job instance in the database and returns this instance."""

        with sqlalchemy.orm.Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)  # Refresh to get the ID
            logger.debug("Submitted new job %s", job)
        return job

    @staticmethod
    def get_jobs_by_status(
        *,
        status: JobStatus,
    ) -> Sequence[sqlalchemy.Row[tuple[Job]]]:
        """Gets all the Job instances with given status."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(Job)
                .where(Job.status == status)
                .options(sqlalchemy.orm.joinedload(Job.experiment_source))
                # .options(sqlalchemy.orm.joinedload(Job.scan_parameters))
                .order_by(Job.priority.asc())
                .order_by(Job.created.asc())
            )
            jobs = session.execute(stmt).all()
            logger.debug("Got jobs filtered by status %s", status)
        return jobs

    @staticmethod
    def get_job_by_experiment_source_and_status(
        *,
        experiment_source_id: int,
        status: JobStatus | list[JobStatus] = [*JobStatus],
    ) -> Sequence[sqlalchemy.Row[tuple[Job]]]:
        """Gets all the Job instances with given experiment_source_id and status."""

        if not isinstance(status, list):
            status = [status]

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(Job)
                .where(Job.experiment_source_id == experiment_source_id)
                .where(Job.status.in_(cast(list[JobStatus], status)))
                .order_by(Job.priority.asc())
                .order_by(Job.created.asc())
                # this somehow creates a USE TEMP B-TREE FOR ORDER BY query, but it is
                # still faster than selectinload
                .options(sqlalchemy.orm.joinedload(Job.experiment_source))
            )

            jobs = session.execute(stmt).all()
            logger.debug("Got jobs by experiment_source_id %s", experiment_source_id)
        return jobs
