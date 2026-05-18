import datetime

import pytz
import sqlalchemy
import sqlalchemy.orm

from icon.config.config import get_config
from icon.server.data_access.models.sqlite.base import Base

timezone = pytz.timezone(get_config().date.timezone)


class TTLMaskState(Base):
    """SQLAlchemy model for persisting TTL override masks.

    A single row (id=1) stores the current high_mask and low_mask written to the
    Zedboard FPGA. This allows the server to restore channel states after a hardware
    power cycle.
    """

    __tablename__ = "ttl_mask_states"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        primary_key=True, autoincrement=True
    )
    high_mask: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        nullable=False, default=0
    )
    low_mask: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        nullable=False, default=0
    )
    updated_at: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        nullable=False,
        default=lambda: datetime.datetime.now(timezone),
        onupdate=lambda: datetime.datetime.now(timezone),
    )

    def __repr__(self) -> str:
        return (
            f"<TTLMaskState high_mask=0x{self.high_mask:08x} "
            f"low_mask=0x{self.low_mask:08x} updated_at={self.updated_at}>"
        )
