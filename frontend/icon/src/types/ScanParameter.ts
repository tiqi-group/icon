import { Job } from "./Job";

export interface ScanParameter {
  id: number;
  job_id: number;
  name: string;
  scan_values: number[];
  variable_id: string;
  device_id?: number | null;
  device?: { id: number; name: string } | null;
  job?: Job;
  realtime: boolean;
}
