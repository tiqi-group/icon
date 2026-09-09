import datetime
import logging
from collections.abc import Sequence

import pytz
import sqlalchemy.orm
from sqlalchemy import func, select, update

from icon.config.config import get_config
from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.job_list_item import JobListItemDict
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)

timezone = pytz.timezone(get_config().date.timezone)


def _job_list_item(
    *,
    job_id: int,
    created: datetime.datetime,
    status: JobStatus,
    experiment_id: str,
    num_scan_parameters: int,
    run: tuple[int, JobRunStatus] | None,
) -> JobListItemDict:
    """Build a job list item from raw column values."""
    return {
        "id": job_id,
        "created": SQLAlchemyDictEncoder.encode(created),
        "status": status.value,
        "experiment_id": experiment_id,
        "num_scan_parameters": num_scan_parameters,
        "run_id": run[0] if run is not None else None,
        "run_status": run[1].value if run is not None else None,
    }


class JobRepository:
    """Repository for `Job` entities.

    Encapsulates SQLAlchemy session/query logic and emits Socket.IO events on changes.
    All methods open their own session and return detached ORM objects.
    """

    @staticmethod
    def submit_job(*, job: Job) -> Job:
        """Insert a new job and emit a creation event.

        Args:
            job: The job instance to persist.

        Returns:
            The persisted job with generated fields populated.
        """
        with sqlalchemy.orm.Session(engine) as session:
            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)

            logger.debug("Submitted new job %s", job)

        emit_queue.put(
            {
                "event": "job.new",
                "data": {
                    "job": SQLAlchemyDictEncoder.encode(
                        JobRepository.get_job_by_id(
                            job_id=job.id,
                            load_experiment_source=True,
                            load_scan_parameters=True,
                        )
                    ),
                },
            }
        )

        return job

    @staticmethod
    def resubmit_job_by_id(*, job_id: int) -> Job:
        """Clone an existing job as a new submission.

        If the source job is not itself a resubmission, the new job's `parent_job_id` is
        set to the original job's id.

        Args:
            job_id: ID of the job to clone.

        Returns:
            The newly created job.
        """
        with sqlalchemy.orm.Session(engine) as session:
            job = session.execute(
                sqlalchemy.select(Job).where(Job.id == job_id)
            ).scalar_one()
            sqlalchemy.orm.make_transient(job)

            if not job.parent_job_id:
                job.parent_job_id = job.id

            # PK and created are set by DB on insert
            job.id = None  # type: ignore
            job.created = None  # type: ignore

            session.add(job)
            session.commit()
            session.refresh(job)
            session.expunge(job)

        emit_queue.put(
            {
                "event": "job.new",
                "data": {
                    "job": SQLAlchemyDictEncoder.encode(
                        JobRepository.get_job_by_id(
                            job_id=job.id,
                            load_experiment_source=True,
                            load_scan_parameters=True,
                        )
                    ),
                },
            }
        )

        return job

    @staticmethod
    def update_job_status(*, job: Job, status: JobStatus) -> Job:
        """Update a job's status and emit an update event.

        Args:
            job: Job to update (identified by its `id`).
            status: New job status.

        Returns:
            The updated job with relationships loaded.
        """
        with sqlalchemy.orm.Session(engine) as session:
            session.execute(update(Job).where(Job.id == job.id).values(status=status))
            session.commit()

            job = (
                session.execute(
                    select(Job)
                    .where(Job.id == job.id)
                    .options(
                        sqlalchemy.orm.joinedload(Job.experiment_source),
                        sqlalchemy.orm.joinedload(Job.scan_parameters),
                    )
                )
                .unique()
                .scalar_one()
            )
            session.expunge(job)

            logger.debug("Updated job %s", job)

        emit_queue.put(
            {
                "event": "job.update",
                "data": {
                    "job_id": job.id,
                    "updated_properties": {"status": status.value},
                },
            }
        )

        return job

    @staticmethod
    def get_jobs_by_status_and_timeframe(
        *,
        status: JobStatus | None = None,
        start: datetime.datetime | None = None,
        stop: datetime.datetime | None = None,
    ) -> Sequence[Job]:
        """List jobs filtered by status and optional creation time window.

        Args:
            status: Optional status filter.
            start: Inclusive start timestamp.
            stop: Exclusive stop timestamp.

        Returns:
            Matching jobs ordered by priority then creation time.
        """
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

            return session.execute(stmt).unique().scalars().all()

    @staticmethod
    def get_job_list(
        *,
        statuses: Sequence[JobStatus] | None = None,
        before_id: int | None = None,
        limit: int | None = None,
    ) -> list[JobListItemDict]:
        """List jobs as lightweight `JobListItemDict` items.

        Pagination is cursor-based on `Job.id`.

        Args:
            statuses: Optional status filter; jobs matching any of the given
                statuses are returned.
            before_id: Exclusive upper bound on the job ID; pass the lowest ID of
                the previous page to fetch the next one.
            limit: Maximum number of jobs to return.

        Returns:
            Job list entries ordered by descending job ID.
        """
        stmt = (
            select(
                Job.id,
                Job.created,
                Job.status,
                ExperimentSource.experiment_id,
            )
            .join(ExperimentSource, Job.experiment_source_id == ExperimentSource.id)
            .order_by(Job.id.desc())
        )

        if statuses is not None:
            stmt = stmt.where(Job.status.in_(statuses))
        if before_id is not None:
            stmt = stmt.where(Job.id < before_id)
        if limit is not None:
            stmt = stmt.limit(limit)

        with sqlalchemy.orm.Session(engine) as session:
            rows = session.execute(stmt).all()
            if not rows:
                return []

            job_ids = [row.id for row in rows]
            lowest, highest = min(job_ids), max(job_ids)

            scan_parameter_counts: dict[int, int] = dict(
                session.execute(
                    select(ScanParameter.job_id, func.count(ScanParameter.id))
                    .where(ScanParameter.job_id.between(lowest, highest))
                    .group_by(ScanParameter.job_id)
                ).all()  # type: ignore[arg-type]
            )

            latest_runs: dict[int, tuple[int, JobRunStatus]] = {
                run.job_id: (run.id, run.status)
                for run in session.execute(
                    select(JobRun.job_id, JobRun.id, JobRun.status)
                    .where(JobRun.job_id.between(lowest, highest))
                    .order_by(JobRun.scheduled_time.asc())
                ).all()
            }

        return [
            _job_list_item(
                job_id=row.id,
                created=row.created,
                status=row.status,
                experiment_id=row.experiment_id,
                num_scan_parameters=scan_parameter_counts.get(row.id, 0),
                run=latest_runs.get(row.id),
            )
            for row in rows
        ]

    @staticmethod
    def get_job_by_id(
        *,
        job_id: int,
        load_experiment_source: bool = False,
        load_scan_parameters: bool = False,
    ) -> Job:
        """Fetch a job by ID with optional eager-loading.

        Args:
            job_id: Job identifier.
            load_experiment_source: If True, eager-load `experiment_source`.
            load_scan_parameters: If True, eager-load `scan_parameters`.

        Returns:
            The requested job.
        """
        with sqlalchemy.orm.Session(engine) as session:
            stmt = select(Job).where(Job.id == job_id)

            if load_experiment_source:
                stmt = stmt.options(sqlalchemy.orm.joinedload(Job.experiment_source))
            if load_scan_parameters:
                stmt = stmt.options(sqlalchemy.orm.joinedload(Job.scan_parameters))

            return session.execute(stmt).unique().scalar_one()

    @staticmethod
    def get_job_by_experiment_source_and_status(
        *,
        experiment_source_id: int,
        status: JobStatus | None = None,
    ) -> Sequence[sqlalchemy.Row[tuple[Job]]]:
        """List jobs for an experiment source, optionally filtered by status.

        Args:
            experiment_source_id: Foreign key of the experiment source.
            status: Optional status filter.

        Returns:
            Rows containing `Job` objects, ordered by priority then creation time.
        """
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
