import { JobRunStatus, JobStatus } from "./enums";

/**
 * A job list element. Represents the data shown in the job list.
 */
export interface JobListItem {
  id: number;
  created: string;
  status: JobStatus;
  experiment_id: string;
  num_scan_parameters: number;
  /** ID of the job's latest run, used to route `job_run.update` events. */
  run_id: number | null;
  /** Status of the latest run, or null if the job has not run yet. */
  run_status: JobRunStatus | null;
}
