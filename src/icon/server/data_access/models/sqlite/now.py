import datetime


def now() -> datetime.datetime:
    """Timezone-aware UTC timestamp used as a SQLAlchemy column default."""
    return datetime.datetime.now(datetime.UTC)
