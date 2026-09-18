import { ScanParameter } from "../types/ScanParameter";
import { ScanMode } from "../types/enums";

/**
 * Determines whether a job's scan parameters are being correlated: stepped through
 * all at once, producing a one-dimensional list of data points, rather than combined
 * into a mesh.
 *
 * This requires at least two non-realtime parameters — a single parameter has
 * nothing to correlate with, and zero parameters aren't a scan at all. A realtime
 * parameter is scanned as an outer loop and keeps its own axis, so it doesn't count
 * towards correlation.
 *
 * @param scanParameters - The job's scan parameters.
 * @param scanMode - The job's scan mode.
 * @returns Whether the parameters are correlated (and so should be presented as 1D).
 */
export function isCorrelatedScan(
  scanParameters: ScanParameter[] | undefined,
  scanMode: ScanMode | undefined,
): boolean {
  const params = scanParameters ?? [];
  return (
    scanMode === ScanMode.CORRELATED &&
    params.length > 1 &&
    !params.some((param) => param.realtime)
  );
}
