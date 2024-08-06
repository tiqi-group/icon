import datetime
from typing import Any, ClassVar

import sqlalchemy
import sqlalchemy.orm


class Base(sqlalchemy.orm.DeclarativeBase):
    # https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#customizing-the-type-map
    type_annotation_map: ClassVar[dict[type, Any]] = {
        datetime.datetime: sqlalchemy.TIMESTAMP(timezone=True),
    }
