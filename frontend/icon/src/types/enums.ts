export enum DeviceStatus {
  ENABLED = "enabled",
  DISABLED = "disabled",
}

export enum JobStatus {
  SUBMITTED = "submitted",
  PROCESSING = "processing",
  PROCESSED = "processed",
}

export enum ScanMode {
  MESH = "mesh",
  CORRELATED = "correlated",
}

export enum JobRunStatus {
  PENDING = "pending",
  PROCESSING = "processing",
  FAILED = "failed",
  CANCELLED = "cancelled",
  DONE = "done",
  PAUSED = "paused",
}
