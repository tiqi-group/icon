import { ScanPattern } from "./ScanParameterInfo";

export interface ScanParameterGenerationSpec {
  start: number;
  stop: number;
  points: number;
  pattern: ScanPattern;
}
