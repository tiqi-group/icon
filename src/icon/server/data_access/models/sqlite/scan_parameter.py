import json
from typing import TYPE_CHECKING, Any

import sqlalchemy
import sqlalchemy.orm

from icon.server.data_access.models.sqlite.base import Base

if TYPE_CHECKING:
    from icon.server.data_access.models.sqlite.job import Job


class JSONEncodedList(sqlalchemy.TypeDecorator):
    """Custom SQLAlchemy type for storing lists as JSON-encoded strings."""

    impl = sqlalchemy.TEXT

    cache_ok = True  # Cache optimization

    def process_bind_param(self, value: Any, dialect: sqlalchemy.Dialect) -> str:
        if value is None:
            value = []
        if not isinstance(value, list):
            raise ValueError("Value must be a list.")
        return json.dumps(value)

    def process_result_value(
        self, value: Any, dialect: sqlalchemy.Dialect
    ) -> list[str]:
        if value is None:
            return []
        return json.loads(value)


class ScanParameter(Base):
    __tablename__ = "scan_parameters"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )

    job_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.ForeignKey("job_submissions.id")
    )
    job: sqlalchemy.orm.Mapped["Job"] = sqlalchemy.orm.relationship(
        back_populates="scan_parameters"
    )
    variable_id: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    scan_values: sqlalchemy.orm.Mapped[list[float]] = sqlalchemy.orm.mapped_column(
        JSONEncodedList, nullable=False
    )
    # remote_source_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
    #     sqlalchemy.ForeignKey("remote_sources.id")
    # )
    # remote_source: sqlalchemy.orm.Mapped["RemoteSource"] = sqlalchemy.orm.relationship()

    def __repr__(self) -> str:
        return f"<Parameter '{self.variable_id}'>"
