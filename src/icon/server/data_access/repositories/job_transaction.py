import logging
from datetime import datetime

import sqlalchemy.orm
from sqlalchemy import select, update

from icon.server.data_access.db_context.sqlite import engine
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun, timezone
from icon.server.data_access.sqlalchemy_dict_encoder import SQLAlchemyDictEncoder
from icon.server.web_server.socketio_emit_queue import emit_queue

logger = logging.getLogger(__name__)


class JobTransaction:
    @staticmethod
    def insert_run_from_jobid(*, job_: Job) -> tuple[Job, JobRun]:
        """Atomically insert a run for a given job ID and mark the job as PROCESSING.

        Args:
            job_: The job for which to create the run.

        Returns:
            A tuple of the updated Job and the newly created JobRun.
        """
        with sqlalchemy.orm.Session(engine, expire_on_commit=False) as session, session.begin():
            session.execute(
                update(Job).where(Job.id == job_.id).values(status=JobStatus.PROCESSING)
            )
            job = (
                session.execute(
                    select(Job)
                    .where(Job.id == job_.id)
                    .options(
                        sqlalchemy.orm.joinedload(Job.experiment_source),
                        sqlalchemy.orm.joinedload(Job.scan_parameters),
                    )
                )
                .unique()
                .scalar_one()
            )

            run = JobRun(job_id=job.id, scheduled_time=datetime.now(tz=timezone))
            session.add(run)
            session.flush()  # populate run.id before building the task
            session.expunge(job)
            session.expunge(run)

        emit_queue.put(
            {
                "event": "job.update",
                "data": {
                    "job_id": job.id,
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
