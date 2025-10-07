import { Job } from "./Job";

export interface ScanParameter {
  id: number;
  job_id: number;
  scan_values: number[];
  variable_id: string;
  job?: Job;
  realtime: boolean;
}
