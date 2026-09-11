import { Job } from "./Job";
import { JobRunStatus } from "./enums";

export interface JobRun {
  id: number;
  scheduled_time: string;
  job_id: number;
  job: Job;
  status: JobRunStatus;
  log?: string | null;
}
