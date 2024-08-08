import logging
from collections.abc import Sequence

import sqlalchemy.orm
from sqlalchemy import select

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobIterationStatus
from icon.server.data_access.models.sqlite.job_iteration import JobIteration

logger = logging.getLogger(__name__)


class JobIterationRepository:
    @staticmethod
    def insert_iteration(
        *,
        iteration: JobIteration,
    ) -> JobIteration:
        """Creates a new JobIteration instance in the database and returns this
        instance.
        """

        with sqlalchemy.orm.Session(engine) as session:
            session.add(iteration)
            session.commit()
            session.refresh(iteration)  # Refresh to get the ID
            logger.debug("Created new iteration %s", iteration)
        return iteration

    @staticmethod
    def update_iteration(
        *,
        iteration: JobIteration,
        status: JobIterationStatus,
        log: str | None = None,
    ) -> JobIteration:
        """Updates a JobIteration instance in the database and returns this
        instance.
        """

        with sqlalchemy.orm.Session(engine) as session:
            iteration.status = status
            iteration.log = log
            session.flush()

            logger.debug("Updated iteration %s", iteration)
        return iteration

    @staticmethod
    def get_iterations_by_status(
        *,
        status: JobIterationStatus,
        load_job: bool = False,
    ) -> Sequence[sqlalchemy.Row[tuple[JobIteration]]]:
        """Gets all the JobIteration instances with given status."""
        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(JobIteration)
                .where(JobIteration.status == status)
                .order_by(JobIteration.priority.asc())
                .order_by(JobIteration.scheduled_time.asc())
            )

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobIteration.job))

            iterations = session.execute(stmt).all()
            logger.debug("Got JobIterations filtered by status %s", status)
        return iterations

    @staticmethod
    def get_iterations_by_job_id_and_status(
        *,
        job_id: int,
        status: JobIterationStatus | None = None,
        load_job: bool = False,
    ) -> Sequence[sqlalchemy.Row[tuple[JobIteration]]]:
        """Gets all the JobIteration instances with given job_id and status."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(JobIteration).where(JobIteration.job_id == job_id)

            if status:
                stmt = stmt.where(JobIteration.status == status)

            if load_job:
                stmt = stmt.options(sqlalchemy.orm.joinedload(JobIteration.job))

            stmt = stmt.order_by(
                JobIteration.priority.asc(), JobIteration.scheduled_time.asc()
            )

            iterations = session.execute(stmt).all()
            logger.debug("Got JobIterations by job_id %s", job_id)
        return iterations
