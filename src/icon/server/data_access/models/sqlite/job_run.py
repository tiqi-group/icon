import datetime
from typing import TYPE_CHECKING

import pytz
import sqlalchemy
import sqlalchemy.orm

from icon.config.config import get_config
from icon.server.data_access.models.enums import JobRunStatus
from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job

timezone = pytz.timezone(get_config().date.timezone)


class JobRun(Base):
    """SQLAlchemy model for job runs.

    Represents the execution of a job, including its scheduled time, current status, and
    log messages.

    Constraints:
        - Indexed by `(job_id, status, scheduled_time)`.
        - `scheduled_time` must be unique across runs.
    """

    __tablename__ = "job_runs"
    __table_args__ = (
        sqlalchemy.Index(
            "by_job_id_and_status",
            "job_id",
            "status",
            "scheduled_time",
        ),
        sqlalchemy.UniqueConstraint("scheduled_time", name="unique_scheduled_time"),
    )

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    """Primary key identifier for the job run."""

    scheduled_time: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(default=datetime.datetime.now(timezone))
    )
    """Time when the run was scheduled to start."""

    job_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id")
    )
    """Foreign key referencing the job being executed."""

    job: sqlalchemy.orm.Mapped["Job"] = sqlalchemy.orm.relationship(
        back_populates="run"
    )
    """Relationship to the job associated with this run."""

    status: sqlalchemy.orm.Mapped[JobRunStatus] = sqlalchemy.orm.mapped_column(
        default=JobRunStatus.PENDING
    )
    """Current status of the run (pending, processing, cancelled, etc.)."""

    log: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(default=None)
    """Optional log message for this run (e.g., cancellation reason)."""

    def __repr__(self) -> str:
        return (
            f"<JobRun id={self.id} "
            f"scheduled_time={self.scheduled_time} status={self.status}>"
        )
