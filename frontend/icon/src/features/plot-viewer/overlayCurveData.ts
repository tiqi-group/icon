import type { HeatmapCell, HeatmapData } from "./heatmapData";

export type OverlayHorizontalAxis = "x" | "y";
export type OverlayCurvePoint = [number, number | null, number];
export interface OverlayCurve {
  id: string;
  label: string;
  fixedValue: number;
  points: OverlayCurvePoint[];
}

function observedCells(model: HeatmapData, channelName: string): HeatmapCell[] {
  return (
    model.channels.find((channel) => channel.name === channelName)?.cells ?? []
  ).filter(
    (cell) =>
      Number.isFinite(cell.x) &&
      Number.isFinite(cell.y) &&
      Number.isFinite(cell.value) &&
      Number.isFinite(cell.count) &&
      cell.count > 0,
  );
}

/** Only offer slices with actual finite observations for the selected channel. */
export function availableCurveSlices(
  model: HeatmapData,
  channelName: string,
  horizontalAxis: OverlayHorizontalAxis,
): number[] {
  const fixedAxis = horizontalAxis === "x" ? "y" : "x";
  return [
    ...new Set(observedCells(model, channelName).map((cell) => cell[fixedAxis])),
  ].sort((a, b) => a - b);
}

/** Preserve full numeric precision and timestamp milliseconds in legend/control labels. */
export function curveSliceLabel(
  model: HeatmapData,
  horizontalAxis: OverlayHorizontalAxis,
  fixedValue: number,
): string {
  const axis = horizontalAxis === "x" ? model.yAxis : model.xAxis;
  const date = new Date(fixedValue);
  const coordinate =
    axis.realtime && Number.isFinite(date.getTime())
      ? date.toISOString()
      : String(fixedValue);
  return `${axis.name} = ${coordinate}`;
}

/**
 * Overlay measured values on one shared scale without offsets or synthetic values.
 * Each missing numeric-grid run needs one null to break a line (connectNulls stays false).
 * Realtime axes have no planned timestamp grid, so other slices cannot imply gaps.
 * Numeric leading/trailing nulls retain the domain without expanding a Cartesian grid.
 */
export function buildOverlayCurves(
  model: HeatmapData,
  channelName: string,
  horizontalAxis: OverlayHorizontalAxis,
  selectedValues: number[],
): OverlayCurve[] {
  const selected = [...new Set(selectedValues.filter(Number.isFinite))].sort(
    (a, b) => a - b,
  );
  const channel = model.channels.find((item) => item.name === channelName);
  if (!channel || !selected.length) return [];
  const cells = observedCells(model, channelName);
  const fixedAxis = horizontalAxis === "x" ? "y" : "x";
  const horizontal = horizontalAxis === "x" ? model.xAxis : model.yAxis;
  const coordinates = horizontal.realtime
    ? []
    : [
        ...new Set([
          ...horizontal.values.filter(Number.isFinite),
          ...cells.map((cell) => cell[horizontalAxis]),
        ]),
      ].sort((a, b) => a - b);
  const positions = new Map(coordinates.map((value, index) => [value, index]));
  const wanted = new Set(selected);
  const slices = new Map<number, HeatmapCell[]>();
  for (const cell of cells) {
    if (!wanted.has(cell[fixedAxis])) continue;
    const slice = slices.get(cell[fixedAxis]);
    if (slice) slice.push(cell);
    else slices.set(cell[fixedAxis], [cell]);
  }
  return selected.map((fixedValue) => {
    const slice = (slices.get(fixedValue) ?? []).sort(
      (a, b) => a[horizontalAxis] - b[horizontalAxis],
    );
    const points: OverlayCurvePoint[] = [];
    let previousPosition: number | undefined;
    for (const cell of slice) {
      if (!horizontal.realtime) {
        const position = positions.get(cell[horizontalAxis])!;
        if (previousPosition === undefined && position > 0) {
          points.push([coordinates[0], null, 0]);
        } else if (previousPosition !== undefined && position > previousPosition + 1) {
          points.push([coordinates[previousPosition + 1], null, 0]);
        }
        previousPosition = position;
      }
      points.push([cell[horizontalAxis], cell.value, cell.count]);
    }
    if (previousPosition !== undefined && previousPosition < coordinates.length - 1) {
      points.push([coordinates[coordinates.length - 1], null, 0]);
    }
    return {
      id: `overlay-${JSON.stringify([horizontalAxis, channelName, fixedValue])}`,
      label: curveSliceLabel(model, horizontalAxis, fixedValue),
      fixedValue,
      points,
    };
  });
}
