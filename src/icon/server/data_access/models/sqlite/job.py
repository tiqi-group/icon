import datetime
from typing import TYPE_CHECKING

import pytz
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm

from icon.config.config import get_config
from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
    from icon.server.data_access.models.sqlite.job_run import JobRun
    from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter

timezone = pytz.timezone(get_config().date.timezone)


class Job(Base):
    """SQLAlchemy model for experiment jobs.

    Represents a scheduled or running experiment job, including its metadata,
    status, and relationships to experiment sources, runs, and scan parameters.

    Constraints:
        - `priority` must be between 0 and 20.
        - Indexed by `(experiment_source_id, status, priority, created)`.
    """

    __tablename__ = "job_submissions"
    __table_args__ = (
        sqlalchemy.Index(
            "by_experiment_id_and_status",
            "experiment_source_id",
            "status",
            "priority",
            "created",
        ),
        sqlalchemy.CheckConstraint("priority >= 0", name="priority_ge_0"),
        sqlalchemy.CheckConstraint("priority <= 20", name="priority_le_20"),
    )

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    """Primary key identifier for the job."""

    created: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        default=lambda: datetime.datetime.now(timezone)
    )
    """Timestamp when the job was created. This cannot be set manually."""
    # user_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
    #     sqlalchemy.ForeignKey("user.id"),
    #     default=None,
    # )
    experiment_source_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("experiment_sources.id")
    )
    """Foreign key referencing the associated experiment source."""

    experiment_source: sqlalchemy.orm.Mapped["ExperimentSource"] = (
        sqlalchemy.orm.relationship(back_populates="jobs")
    )
    """Relationship to the experiment source."""

    status: sqlalchemy.orm.Mapped[JobStatus] = sqlalchemy.orm.mapped_column(
        default=JobStatus.SUBMITTED
    )
    """Current status of the job (submitted, processing, etc.)."""

    git_commit_hash: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(
        default=None
    )
    """Git commit hash of the experiment code associated with the job."""

    priority: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        default=20,
    )
    """Job priority, between 0 (lowest) and 20 (highest)."""

    repetitions: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        default=1,
    )
    """Number of times the experiment should be repeated."""

    number_of_shots: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        default=50,
    )
    """Number of shots per repetition."""

    local_parameters_timestamp: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(default=datetime.datetime.now(timezone))
    )
    """Timestamp of the local parameter snapshot used for this job."""

    auto_calibration: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False
    )
    """Whether auto-calibration is enabled for this job. Currently unused."""

    run: sqlalchemy.orm.Mapped["JobRun"] = sqlalchemy.orm.relationship(
        back_populates="job"
    )
    """Relationship to the job run associated with this job."""

    debug_mode: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False
    )
    """Whether the job was submitted in debug mode (no commit hash)."""

    scan_parameters: sqlalchemy.orm.Mapped[list["ScanParameter"]] = (
        sqlalchemy.orm.relationship(back_populates="job")
    )
    """List of scan parameters associated with this job."""

    parent_job_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id"), nullable=True
    )
    """Foreign key referencing the original job if this job was resubmitted."""

    parent_job: sqlalchemy.orm.Mapped["Job | None"] = sqlalchemy.orm.relationship(
        "Job", remote_side=[id], back_populates="resubmitted_jobs"
    )
    """Relationship to the parent job from which this job was resubmitted."""

    resubmitted_jobs: sqlalchemy.orm.Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        "Job", back_populates="parent_job"
    )
    """List of jobs resubmitted from this job."""

    def __repr__(self) -> str:
        return (
            f"<Job id={self.id} priority={self.priority} "
            f"created={self.created} status={self.status}>"
        )


@sqlalchemy.event.listens_for(Job, "before_insert")
def receive_before_insert(
    mapper: sqlalchemy.orm.Mapper[Job],
    connection: sqlalchemy.engine.Connection,
    target: Job,
) -> None:
    """Prevent manually setting the 'created' field on insert."""
    if target.created:
        raise ValueError(f"Cannot set 'created' on {Job}")
