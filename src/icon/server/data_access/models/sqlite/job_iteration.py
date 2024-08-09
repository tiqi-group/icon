import datetime
from typing import TYPE_CHECKING

import pytz
import sqlalchemy
import sqlalchemy.event
import sqlalchemy.orm

from icon.server.data_access.models.enums import JobIterationStatus
from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job

zurich_timezone = pytz.timezone("Europe/Zurich")


class JobIteration(Base):
    __tablename__ = "job_iterations"
    __table_args__ = (
        sqlalchemy.Index(
            "by_job_id_and_status",
            "job_id",
            "status",
            "scheduled_time",
        ),
    )

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    scheduled_time: sqlalchemy.orm.Mapped[datetime.datetime] = (
        sqlalchemy.orm.mapped_column(default=datetime.datetime.now(zurich_timezone))
    )
    job_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id")
    )
    job: sqlalchemy.orm.Mapped["Job"] = sqlalchemy.orm.relationship(
        back_populates="iterations"
    )
    status: sqlalchemy.orm.Mapped[JobIterationStatus] = sqlalchemy.orm.mapped_column(
        default=JobIterationStatus.PENDING
    )
    log: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(default=None)

    def __repr__(self) -> str:
        return (
            f"<JobIteration id={self.id} "
            f"scheduled_time={self.scheduled_time} status={self.status}>"
        )
