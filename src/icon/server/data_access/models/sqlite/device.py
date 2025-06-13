import datetime

import pytz
import sqlalchemy
import sqlalchemy.orm

from icon.config.config import get_config
from icon.server.data_access.models.enums import DeviceStatus
from icon.server.data_access.models.sqlite.base import Base

timezone = pytz.timezone(get_config().date.timezone)


class Device(Base):
    __tablename__ = "devices"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    created: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        default=lambda: datetime.datetime.now(timezone)
    )
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(
        unique=True, index=True
    )
    url: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column()
    status: sqlalchemy.orm.Mapped[DeviceStatus] = sqlalchemy.orm.mapped_column(
        default=DeviceStatus.ENABLED,
        index=True,
    )
    description: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(
        default=None
    )

    def __repr__(self) -> str:
        return (
            f"<Device id={self.id} name={self.name} url={self.url} "
            f"created={self.created} status={self.status}>"
        )
