import datetime

import pytz

from icon.config.config import get_config


def now() -> datetime.datetime:
    timezone = pytz.timezone(get_config().date.timezone)
    return datetime.datetime.now(timezone)
