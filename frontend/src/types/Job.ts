import { JobStatus } from "./enums";
import { ExperimentSource } from "./ExperimentSource";
import { ScanParameter } from "./ScanParameter";

export interface Job {
  auto_calibration: boolean;
  created: string;
  debug_mode: boolean;
  experiment_source: ExperimentSource;
  experiment_source_id: number;
  git_commit_hash?: string | null;
  id: number;
  local_parameters_timestamp: string;
  parent_job_id?: number | null;
  priority: number;
  repetitions: number;
  scan_parameters: ScanParameter[];
  status: JobStatus;
}
