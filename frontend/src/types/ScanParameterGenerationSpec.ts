import { ScanInputMode, ScanPattern } from "./ScanParameterInfo";

export interface ScanParameterGenerationSpec {
  start: number;
  stop: number;
  points: number;
  pattern: ScanPattern;
  /** Controls which pair of fields is shown in the UI. "startStop" is the default. */
  inputMode?: ScanInputMode;
}
