import logging

import sqlalchemy.orm
from sqlalchemy import select, update

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobRunStatus, JobStatus
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.models.sqlite.now import now
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)

LIVE_RUN_STATUSES = (
    JobRunStatus.PENDING,
    JobRunStatus.PROCESSING,
    JobRunStatus.PAUSED,
)
"""Run states in which a pre-processing worker still owns the job."""


def _latest_run_id(job_id: int) -> sqlalchemy.ScalarSelect[int]:
    """Select the run a job currently owns.

    Args:
        job_id: ID of the job whose run to select.

    Returns:
        A scalar subquery yielding the newest run's ID.
    """
    return (
        select(JobRun.id)
        .where(JobRun.job_id == job_id)
        .order_by(JobRun.scheduled_time.desc())
        .limit(1)
        .scalar_subquery()
    )


def cancel_job(
    *,
    job_id: int,
    log: str | None = None,
    run_status: JobRunStatus = JobRunStatus.CANCELLED,
) -> None:
    """Cancel a job and move its run to `run_status`.

    Args:
        job_id: ID of the job to retire.
        run_status: Terminal status to give the run.
        log: Reason recorded on the run, if there is one.
    """
    with (
        sqlalchemy.orm.Session(engine, expire_on_commit=False) as session,
        session.begin(),
    ):
        session.execute(
            update(Job).where(Job.id == job_id).values(status=JobStatus.PROCESSED)
        )

        run = session.execute(
            update(JobRun)
            .where(JobRun.id == _latest_run_id(job_id))
            .where(JobRun.status.in_(LIVE_RUN_STATUSES))
            .values(status=run_status, log=log)
            .returning(JobRun)
        ).scalar_one_or_none()

    logger.debug(
        "Cancelled job %s, run %s is %s",
        job_id,
        run.id if run is not None else None,
        run_status.value,
    )

    emit_queue.put(
        {
            "event": "job.update",
            "data": {
                "job_id": job_id,
                "updated_properties": {"status": JobStatus.PROCESSED.value},
            },
        }
    )

    if run is not None:
        emit_queue.put(
            {
                "event": "job_run.update",
                "data": {
                    "run_id": run.id,
                    "updated_properties": {
                        "status": run_status.value,
                        "log": log,
                    },
                },
            }
        )


def fail_job(*, job_id: int, log: str | None = None) -> None:
    """Cancel job and fail the run it may own.

    Args:
        job_id: ID of the job to fail.
        log: Optional reason recorded on the run.
    """
    cancel_job(job_id=job_id, run_status=JobRunStatus.FAILED, log=log)


def dispatch_job(*, job_id: int) -> tuple[Job, JobRun] | None:
    """Insert a run for a SUBMITTED job and progress it to PROCESSING.

    Args:
        job_id: ID of the job to dispatch.

    Returns:
        The claimed job with its relationships loaded and its new run, or None
        when the job is no longer SUBMITTED, i.e. cancelled or processing.
    """
    with (
        sqlalchemy.orm.Session(engine, expire_on_commit=False) as session,
        session.begin(),
    ):
        claimed_id = session.execute(
            update(Job)
            .where(Job.id == job_id, Job.status == JobStatus.SUBMITTED)
            .values(status=JobStatus.PROCESSING)
            .returning(Job.id)
        ).scalar_one_or_none()

        if claimed_id is None:
            return None

        run = JobRun(job_id=job_id, scheduled_time=now())
        session.add(run)
        session.flush()

        job = (
            session.execute(
                select(Job)
                .where(Job.id == job_id)
                .options(
                    sqlalchemy.orm.joinedload(Job.experiment_source),
                    sqlalchemy.orm.joinedload(Job.scan_parameters),
                )
            )
            .unique()
            .scalar_one()
        )

    logger.debug("Dispatched job %s as run %s", job_id, run.id)

    emit_queue.put(
        {
            "event": "job.update",
            "data": {
                "job_id": job_id,
                "updated_properties": {"status": JobStatus.PROCESSING.value},
            },
        }
    )
    emit_queue.put(
        {
            "event": "job_run.new",
            "data": {"job_run": SQLAlchemyDictEncoder.encode(obj=run)},
        }
    )

    return job, run
