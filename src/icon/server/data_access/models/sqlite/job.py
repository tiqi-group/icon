import datetime
from typing import TYPE_CHECKING

import pytz
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm

from icon.server.data_access.models.enums import JobStatus
from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
    from icon.server.data_access.models.sqlite.job_run import JobRun

zurich_timezone = pytz.timezone("Europe/Zurich")


class Job(Base):
    __tablename__ = "job_submissions"
    __table_args__ = (
        # used by JobRepository.get_jobs_by_status and
        # JobRepository.get_job_by_experiment_source_and_status
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
    created: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        default=datetime.datetime.now(zurich_timezone)
    )
    # user_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
    #     sqlalchemy.ForeignKey("user.id"),
    #     default=None,
    # )
    experiment_source_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("experiment_sources.id")
    )
    experiment_source: sqlalchemy.orm.Mapped["ExperimentSource"] = (
        sqlalchemy.orm.relationship(back_populates="jobs")
    )
    status: sqlalchemy.orm.Mapped[JobStatus] = sqlalchemy.orm.mapped_column(
        default=JobStatus.SUBMITTED
    )
    git_commit_hash: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(
        default=None
    )
    priority: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        default=20,
    )
    local_parameters_timestamp: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(default=datetime.datetime.now(zurich_timezone))
    )
    auto_calibration: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False
    )
    run: sqlalchemy.orm.Mapped["JobRun"] = sqlalchemy.orm.relationship(
        back_populates="job"
    )
    debug_mode: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False
    )
    # scan_parameters: sqlalchemy.orm.Mapped[list[ScanParameter]] = (
    #     sqlalchemy.orm.relationship(back_populates="job")
    # )

    parent_job_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id"), nullable=True
    )
    """Job ID of the original job from which this job was resubmitted"""
    parent_job: sqlalchemy.orm.Mapped["Job | None"] = sqlalchemy.orm.relationship(
        "Job", remote_side=[id], back_populates="resubmitted_jobs"
    )
    resubmitted_jobs: sqlalchemy.orm.Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        "Job", back_populates="parent_job"
    )

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
    if target.created:
        raise ValueError(f"Cannot set 'created' on {Job}")
