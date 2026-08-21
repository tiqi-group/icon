import { ScanParameterGenerationSpec } from "./ScanParameterGenerationSpec";

export const scanPatterns = ["linear", "scatter", "centred", "forwardReverse"] as const;
export type ScanPattern = (typeof scanPatterns)[number];

export const scanInputModes = ["startStop", "spanCenter"] as const;
export type ScanInputMode = (typeof scanInputModes)[number];

export interface ScanParameterInfo {
  id: string;
  deviceNameOrDisplayGroup: string;
  namespace: string;
  generation: ScanParameterGenerationSpec;
  n_scan_points?: number;
}
