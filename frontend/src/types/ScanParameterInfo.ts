export interface ScanParameterInfo {
  id: string;
  values: number[];
  deviceNameOrDisplayGroup: string;
  namespace: string;
  generation: {
    start: number;
    stop: number;
    points: number;
    scatter: boolean;
  };
}
