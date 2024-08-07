import pathlib
from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job


class ExperimentSource(Base):
    __tablename__ = "experiment_sources"
    # https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#declarative-table-configuration
    __table_args__ = (
        sqlalchemy.UniqueConstraint("name", "file_path", name="source_location"),
    )

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    file_path: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    jobs: sqlalchemy.orm.Mapped[list["Job"]] = sqlalchemy.orm.relationship(
        back_populates="experiment_source"
    )

    @sqlalchemy.orm.validates("file_path")
    def validate_file_path(self, key: str, file_path: str | pathlib.Path) -> str:
        if isinstance(file_path, pathlib.Path):
            file_path = str(file_path)

        if "~" in file_path:
            raise ValueError("You cannot use '~' in the file path.")
        return file_path

    def __repr__(self) -> str:
        return f"<Experiment '{self.file_path}: {self.name}'>"
