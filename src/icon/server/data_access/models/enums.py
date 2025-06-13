import enum


class JobStatus(enum.Enum):
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    PROCESSED = "processed"


class JobRunStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"
    CANCELLED = "cancelled"
    DONE = "done"


class SourceType(enum.Enum):
    INFLUXDB = "influxdb"
    PYDASE_SERVICE = "pydase_service"
    TIQI_PLUGIN = "tiqi_plugin"


class DeviceStatus(enum.Enum):
    ENABLED = "enabled"
    DISABLED = "disabled"
