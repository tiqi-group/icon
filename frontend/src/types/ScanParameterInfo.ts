export interface ScanParameterInfo {
  id: string;
  deviceNameOrDisplayGroup: string;
  namespace: string;
  values?: number[];
  generation: {
    start: number;
    stop: number;
    points: number;
    scatter: boolean;
  };
  n_scan_points?: number;
}
