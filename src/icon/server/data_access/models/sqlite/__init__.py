"""This module contains the SQLAlchemy models for ICON.

All models must be imported and added to the ``__all__`` list here so that Alembic can
correctly detect them during schema autogeneration.
Alembic inspects ``Base.metadata``, which is only populated with models that are
actually imported at runtime.
"""

from icon.server.data_access.models.sqlite.base import Base
from icon.server.data_access.models.sqlite.device import Device
from icon.server.data_access.models.sqlite.experiment_source import ExperimentSource
from icon.server.data_access.models.sqlite.job import Job
from icon.server.data_access.models.sqlite.job_run import JobRun
from icon.server.data_access.models.sqlite.scan_parameter import ScanParameter

__all__ = [
    "Base",
    "Device",
    "ExperimentSource",
    "Job",
    "JobRun",
    "ScanParameter",
]
