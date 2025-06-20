import { DeviceStatus } from "./enums";

export interface Device {
  id: number;
  created: string;
  name: string;
  url: string;
  status: DeviceStatus;
  description: string | null;
  reachable: boolean;
}
