export const scanPatterns = ["linear", "scatter", "centred", "forwardReverse"] as const;
export type ScanPattern = (typeof scanPatterns)[number];

export interface ScanParameterInfo {
  id: string;
  values: number[];
  deviceNameOrDisplayGroup: string;
  namespace: string;
  generation: {
    start: number;
    stop: number;
    points: number;
    pattern: ScanPattern;
  };
}
