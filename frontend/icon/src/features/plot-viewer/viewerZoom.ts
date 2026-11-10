export type ZoomAxes = "both" | "x" | "y";

interface ZoomRange {
  id: string;
  start: number;
  end: number;
}

interface ZoomAction {
  dataZoomId: string;
  start: number;
  end: number;
}

interface BrushZoomAction {
  dataZoomId: string;
  startValue: number;
  endValue: number;
}

const clampPercent = (value: number) => Math.max(0, Math.min(100, value));

/** Scale selected axes around their current centres, preserving width at bounds. */
export function scaleZoomRanges(
  ranges: ZoomRange[],
  axes: ZoomAxes,
  factor: number,
): ZoomAction[] {
  if (!Number.isFinite(factor) || factor <= 0) return [];
  return ranges.flatMap(({ id, start, end }) => {
    const selected =
      (id === "viewer-x" && axes !== "y") || (id === "viewer-y" && axes !== "x");
    if (!selected || !Number.isFinite(start) || !Number.isFinite(end)) return [];
    const low = clampPercent(Math.min(start, end));
    const high = clampPercent(Math.max(start, end));
    const width = Math.max(0.1, Math.min(100, (high - low) * factor));
    const centre = (low + high) / 2;
    const nextStart = Math.max(0, Math.min(100 - width, centre - width / 2));
    return [{ dataZoomId: id, start: nextStart, end: nextStart + width }];
  });
}

function numericRange(value: unknown): [number, number] | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const [a, b]: unknown[] = value;
  if (
    typeof a !== "number" ||
    typeof b !== "number" ||
    !Number.isFinite(a) ||
    !Number.isFinite(b) ||
    a === b
  )
    return null;
  return a < b ? [a, b] : [b, a];
}

/** Convert ECharts Cartesian brush coordinates into independent axis zoom actions. */
export function brushZoomRanges(area?: {
  brushType?: string;
  coordRange?: unknown;
}): BrushZoomAction[] {
  const action = (dataZoomId: string, range: [number, number]): BrushZoomAction => ({
    dataZoomId,
    startValue: range[0],
    endValue: range[1],
  });
  if (area?.brushType === "rect") {
    if (!Array.isArray(area.coordRange) || area.coordRange.length !== 2) return [];
    const xRange = numericRange(area.coordRange[0]);
    const yRange = numericRange(area.coordRange[1]);
    return xRange && yRange
      ? [action("viewer-x", xRange), action("viewer-y", yRange)]
      : [];
  }
  if (area?.brushType === "lineX" || area?.brushType === "lineY") {
    const range = numericRange(area.coordRange);
    return range
      ? [action(area.brushType === "lineX" ? "viewer-x" : "viewer-y", range)]
      : [];
  }
  return [];
}
