from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job


class ExperimentSource(Base):
    """SQLAlchemy model for experiment sources.

    Represents a unique experiment identifier from the experiment library. Each
    experiment source may be linked to multiple jobs.
    """

    __tablename__ = "experiment_sources"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    """Primary key identifier for the experiment source."""

    experiment_id: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    """Unique experiment identifier string (as defined in the experiment library)."""

    jobs: sqlalchemy.orm.Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        back_populates="experiment_source"
    )
    """Relationship to jobs associated with this experiment source."""

    def __repr__(self) -> str:
        return f"<Experiment '{self.experiment_id}'>"
