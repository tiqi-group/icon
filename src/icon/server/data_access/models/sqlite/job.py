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

zurich_timezone = pytz.timezone("Europe/Zurich")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        # used by JobRepository.get_jobs_by_status
        sqlalchemy.Index(
            "status_index",
            "status",
            "priority",
            "created",
        ),
        # used by JobRepository.get_job_by_experiment_source_and_status
        sqlalchemy.Index(
            "by_experiment_id_and_status",
            "experiment_source_id",
            "status",
            "priority",
            "created",
        ),
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
        sqlalchemy.CheckConstraint("priority >= 0"),
        sqlalchemy.CheckConstraint("priority <= 20"),
        default=20,
    )
    local_parameters_timestamp: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(default=datetime.datetime.now(zurich_timezone))
    )
    auto_calibration: sqlalchemy.orm.Mapped[bool] = sqlalchemy.orm.mapped_column(
        default=False
    )
    # scan_parameters: sqlalchemy.orm.Mapped[list[ScanParameter]] = (
    #     sqlalchemy.orm.relationship(back_populates="job")
    # )

    def __repr__(self) -> str:
        return (
            f"<Job priority={self.priority} "
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
