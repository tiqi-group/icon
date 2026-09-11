import { DeviceStatus } from "./enums";

export interface DeviceInfo {
  id: number;
  created: string;
  name: string;
  url: string;
  status: DeviceStatus;
  description: string | null;
  retry_attempts: number;
  retry_delay_seconds: number;
  reachable: boolean;
  scannable_params: string[];
}
