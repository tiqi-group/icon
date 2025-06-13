import datetime
import logging
from collections.abc import Sequence

import pytz
import sqlalchemy.orm
from sqlalchemy import select, update

from icon.config.config import get_config
from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.utils.socketio_manager import emit_event

logger = logging.getLogger(__name__)

timezone = pytz.timezone(get_config().date.timezone)


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

        emit_event(
            logger=logger,
            event="new_job",
            data={
                "job": SQLAlchemyDictEncoder.encode(
                    # I need to load experiment_source and scan_parameters here
                    JobRepository.get_job_by_id(
                        job_id=job.id,
                        load_experiment_source=True,
                        load_scan_parameters=True,
                    )
                ),
            },
        )

        return job

    @staticmethod
    def resubmit_job_by_id(*, job_id: int) -> Job:
        """Creates a new job instance in the database, referencing the old (parent) job
        id as parent_job_id, and returns this instance."""
        with sqlalchemy.orm.Session(engine) as session:
            job = session.execute(
                sqlalchemy.select(Job).where(Job.id == job_id)
            ).scalar_one()
            sqlalchemy.orm.make_transient(job)

            # Update the parent_job_id only if the job is not a re-submission itself
            if not job.parent_job_id:
                job.parent_job_id = job.id

            # need to remove primary key and created as they should be set by the
            # databse
            job.id = None  # type: ignore
            job.created = None  # type: ignore

            session.add(job)
            session.commit()
            session.refresh(job)  # Refresh to get the ID

        emit_event(
            logger=logger,
            event="new_job",
            data={
                "job": SQLAlchemyDictEncoder.encode(
                    # I need to load experiment_source and scan_parameters here
                    JobRepository.get_job_by_id(
                        job_id=job.id,
                        load_experiment_source=True,
                        load_scan_parameters=True,
                    )
                ),
            },
        )

        return job

    @staticmethod
    def update_job_status(
        *,
        job: Job,
        status: JobStatus,
    ) -> Job:
        """Updates a job instance in the database and returns this instance."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                update(Job)
                .where(Job.id == job.id)
                .values(status=status)
                .returning(Job)
                .options(sqlalchemy.orm.joinedload(Job.experiment_source))
                .options(sqlalchemy.orm.joinedload(Job.scan_parameters))
            )
            job = session.execute(stmt).scalar_one()
            session.commit()

            logger.debug("Updated job %s", job)

        emit_event(
            logger=logger,
            event="update_job",
            data={
                "job_id": job.id,
                "updated_properties": {"status": status.value},
            },
        )

        return job

    @staticmethod
    def get_jobs_by_status_and_timeframe(
        *,
        status: JobStatus | None = None,
        start: datetime.datetime | None = None,
        stop: datetime.datetime | None = None,
    ) -> Sequence[sqlalchemy.Row[tuple[Job]]]:
        """Gets all the Job instances filtered by status and optional time range."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = (
                select(Job)
                .options(sqlalchemy.orm.joinedload(Job.experiment_source))
                .options(sqlalchemy.orm.joinedload(Job.scan_parameters))
                .order_by(Job.priority.asc())
                .order_by(Job.created.asc())
            )

            if status is not None:
                stmt = stmt.where(Job.status == status)

            if start is not None:
                stmt = stmt.where(Job.created >= start)

            if stop is not None:
                stmt = stmt.where(Job.created < stop)

            return session.execute(stmt).unique().all()

    @staticmethod
    def get_job_by_id(
        *,
        job_id: int,
        load_experiment_source: bool = False,
        load_scan_parameters: bool = False,
    ) -> Job:
        """Gets the Job instances with given id."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(Job).where(Job.id == job_id)

            if load_experiment_source:
                stmt = stmt.options(sqlalchemy.orm.joinedload(Job.experiment_source))
            if load_scan_parameters:
                stmt = stmt.options(sqlalchemy.orm.joinedload(Job.scan_parameters))

            return session.execute(stmt).unique().one()._tuple()[0]

    @staticmethod
    def get_job_by_experiment_source_and_status(
        *,
        experiment_source_id: int,
        status: JobStatus | None = None,
    ) -> Sequence[sqlalchemy.Row[tuple[Job]]]:
        """Gets all the Job instances with given experiment_source_id and status."""

        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(Job).where(Job.experiment_source_id == experiment_source_id)

            if status:
                stmt = stmt.where(Job.status == status)

            stmt = stmt.options(
                sqlalchemy.orm.joinedload(Job.experiment_source)
            ).order_by(Job.priority.asc(), Job.created.asc())

            jobs = session.execute(stmt).all()
            logger.debug("Got jobs by experiment_source_id %s", experiment_source_id)
        return jobs
