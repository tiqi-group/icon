import { ScanPattern } from "./ScanParameterInfo";

export interface ScanParameterValueGenerator {
  start: number;
  stop: number;
  points: number;
  pattern: ScanPattern;
}
