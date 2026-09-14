from typing import TypedDict


class JobListItemDict(TypedDict):
    """A job list item. Minimal, non ORM representation of a job, suitable for fast serialization."""

    id: int
    """Database identifier of the job."""
    created: str
    """Creation timestamp in ISO format."""
    status: str
    """Job status, e.g. "submitted", "processing" or "processed"."""
    experiment_id: str
    """Identifier of the experiment this job runs."""
    num_scan_parameters: int
    """Number of scanned parameters, rendered as the scan dimensionality."""
    run_id: int | None
    """Identifier of the job's latest run, or None if it has not run yet."""
    run_status: str | None
    """Status of the latest run, or None if the job has not run yet."""
