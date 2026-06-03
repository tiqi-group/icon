import { ScanParameterValueGenerator } from "./ScanParameterValueGenerator";

export const scanPatterns = ["linear", "scatter", "centred", "forwardReverse"] as const;
export type ScanPattern = (typeof scanPatterns)[number];

export interface ScanParameterInfo {
  id: string;
  deviceNameOrDisplayGroup: string;
  namespace: string;
  generation: ScanParameterValueGenerator;
  n_scan_points?: number;
}
