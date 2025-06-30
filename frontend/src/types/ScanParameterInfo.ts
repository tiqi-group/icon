export interface ScanParameterInfo {
  id: string;
  values: number[];
  device_name?: string;
  generation: {
    start: number;
    stop: number;
    points: number;
    scatter: boolean;
  };
}
