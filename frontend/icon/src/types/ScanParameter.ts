import { Job } from "./Job";

export interface ScanParameter {
  id: number;
  job_id: number;
  name: string;
  unit?: string | null;
  scan_values: number[];
  variable_id: string;
  job?: Job;
  realtime: boolean;
}
