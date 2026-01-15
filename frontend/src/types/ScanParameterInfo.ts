export const scanPatterns = ["linear", "scatter", "centred", "forwardReverse"] as const;
export type ScanPattern = (typeof scanPatterns)[number];

export interface ScanParameterInfo {
  id: string;
  deviceNameOrDisplayGroup: string;
  namespace: string;
  values?: number[];
  generation: {
    start: number;
    stop: number;
    points: number;
    pattern: ScanPattern;
  };
  n_scan_points?: number;
}
