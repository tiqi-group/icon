from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job


class ExperimentSource(Base):
    __tablename__ = "experiment_sources"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    experiment_id: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    jobs: sqlalchemy.orm.Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        back_populates="experiment_source"
    )

    def __repr__(self) -> str:
        return f"<Experiment '{self.experiment_id}'>"
