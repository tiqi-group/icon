"""Calendar-date bounds for the optional job-list filters."""

from datetime import date, datetime, time, timedelta


def job_date_bounds(
    created_from: str | None, created_to: str | None
) -> tuple[datetime | None, datetime | None]:
    """Inclusive calendar dates in ICON's configured local time (SQLite wall time)."""
    first = date.fromisoformat(created_from) if created_from else None
    last = date.fromisoformat(created_to) if created_to else None
    if last == date.max:
        raise ValueError("Through date must be before 9999-12-31")
    if first is not None and last is not None and first > last:
        raise ValueError("From date must not be after through date")
    return (
        datetime.combine(first, time.min) if first is not None else None,
        datetime.combine(last + timedelta(days=1), time.min)
        if last is not None
        else None,
    )
