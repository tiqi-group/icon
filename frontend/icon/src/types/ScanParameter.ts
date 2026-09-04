import { Job } from "./Job";

export interface ScanParameter {
  id: number;
  job_id: number;
  name: string;
  scan_values: number[];
  variable_id: string;
  job?: Job;
  realtime: boolean;
}
