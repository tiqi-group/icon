export const scanPatterns = ["linear", "scatter", "centred", "forwardReverse"] as const;
export type ScanPattern = (typeof scanPatterns)[number];

export const scanInputModes = ["startStop", "spanCenter"] as const;
export type ScanInputMode = (typeof scanInputModes)[number];

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
    /** Controls which pair of fields is shown in the UI. "startStop" is the default. */
    inputMode?: ScanInputMode;
  };
  n_scan_points?: number;
}
