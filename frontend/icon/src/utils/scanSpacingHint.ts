import { ScanParameterInfo } from "../types/ScanParameterInfo";
import {
  clampToBounds,
  refreshSpanCenterParameters,
  ScanParameterBounds,
} from "./scanUtils";

/** Preview the same re-centering and bounds used when submitting a scan. */
export function scanSpacingHint(
  parameter: ScanParameterInfo,
  bounds: ScanParameterBounds,
  unit: string | undefined,
  liveValue: unknown,
): string | null {
  if (!parameter.id || parameter.namespace === "Real Time") return null;
  const [{ generation }] = refreshSpanCenterParameters([parameter], {
    get: () => (typeof liveValue === "number" ? liveValue : undefined),
  });
  const { start, stop, points, pattern } = generation;
  if (
    ![start, stop, points].every(Number.isFinite) ||
    !Number.isInteger(points) ||
    points < 1
  )
    return null;
  if (points === 1) return "Single point — no step";
  const first = clampToBounds(start, bounds);
  const last = clampToBounds(stop, bounds);
  const step = (last - first) / (points - 1);
  if (!Number.isFinite(step)) return null;
  const label = pattern === "linear" ? "Step size" : "Grid spacing";
  const spacing = pattern === "linear" ? step : Math.abs(step);
  const value = Number(spacing.toPrecision(6));
  const limited = first !== start || last !== stop ? " (limited by bounds)" : "";
  return label + ": " + value + (unit ? " " + unit : "") + limited;
}
