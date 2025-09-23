import datetime
from typing import Any, ClassVar

import sqlalchemy
import sqlalchemy.orm


class Base(sqlalchemy.orm.DeclarativeBase):
    """Base class for all SQLAlchemy ORM models in ICON.

    This class configures the declarative mapping and provides a datetime type mapping
    for all models that inherit from it.
    """

    # https://docs.sqlalchemy.org/en/20/orm/declarative_tables.html#customizing-the-type-map
    type_annotation_map: ClassVar[dict[type, Any]] = {
        datetime.datetime: sqlalchemy.TIMESTAMP(timezone=True),
    }
    """ Custom type mapping used when interpreting Python type annotations.

    Currently, [`datetime.datetime`][] is mapped to
    `sqlalchemy.TIMESTAMP(timezone=True)` to ensure timezone-aware timestamps across all
    models.
    """
