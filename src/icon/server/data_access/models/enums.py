"""This module defines enums used by the SQLAlchemy models.

These enums represent database-level states for jobs, job runs, and devices. They are
stored as strings in the database and used throughout ICON's scheduling and device
management logic.
"""

import enum


class JobStatus(enum.Enum):
    """Lifecycle states of a job submission."""

    SUBMITTED = "submitted"
    """Job has been created and is waiting to be scheduled."""
    PROCESSING = "processing"
    """Job has been put into the pre-processing task queue."""
    PROCESSED = "processed"
    """Job has finished or was cancelled and is no longer active."""


class JobRunStatus(enum.Enum):
    """Lifecycle states of a job run."""

    PENDING = "pending"
    """Run is queued but has not started yet."""
    PROCESSING = "processing"
    """Run is currently executing."""
    FAILED = "failed"
    """Run ended unsuccessfully due to an error."""
    CANCELLED = "cancelled"
    """Run was cancelled before completion."""
    DONE = "done"
    """Run completed successfully."""


class DeviceStatus(enum.Enum):
    """Operational states of a device."""

    ENABLED = "enabled"
    """Device is enabled and may be connected."""
    DISABLED = "disabled"
    """Device is disabled and should not be used."""
