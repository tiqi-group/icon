import type { ExperimentData } from "../../types/ExperimentData";
import type { ScanParameter } from "../../types/ScanParameter";
import { resolveViewerScanMaps } from "./viewerScanParameters";

export interface HeatmapAxis {
  name: string;
  realtime: boolean;
  /** Numeric values, or epoch milliseconds for a realtime axis. */
  values: number[];
}
export interface HeatmapCell {
  x: number;
  y: number;
  value: number;
  count: number;
  pointIndices: number[];
}
export interface HeatmapChannel {
  name: string;
  cells: HeatmapCell[];
  min: number;
  max: number;
}
export interface HeatmapData {
  xAxis: HeatmapAxis;
  yAxis: HeatmapAxis;
  channels: HeatmapChannel[];
  /** Zero-based full raster passes, determined before optional filtering. */
  repetitions: number[];
  period: number | null;
  error?: string;
}

function coordinate(value: unknown, realtime: boolean): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return !realtime || Number.isFinite(new Date(value).getTime()) ? value : null;
  }
  if (realtime && typeof value === "string") {
    const timestamp = Date.parse(value);
    if (Number.isFinite(timestamp)) return timestamp;
  }
  return null;
}

/** The colour domain belongs to the visible channel/cells, with a finite flat-data guard. */
export function heatmapValueRange(cells: HeatmapCell[]): { min: number; max: number } {
  let min = Infinity;
  let max = -Infinity;
  for (const cell of cells) {
    if (!Number.isFinite(cell.value)) continue;
    min = Math.min(min, cell.value);
    max = Math.max(max, cell.value);
  }
  if (min === Infinity) return { min: 0, max: 1 };
  if (min !== max) return { min, max };
  const delta = Math.max(1, Math.abs(min) * 1e-6);
  return Number.isFinite(max + delta)
    ? { min, max: max + delta }
    : { min: min - delta, max };
}

/**
 * Join observed coordinates and readouts by original point index.
 * Planned values define empty categories only; they never assign an observed value.
 */
export function buildHeatmapData(
  data: ExperimentData,
  parameters: ScanParameter[],
  channelNames: string[],
  repetition?: number,
): HeatmapData {
  const [xParameter, yParameter] = parameters;
  const base: HeatmapData = {
    xAxis: {
      name: xParameter?.name ?? "X",
      realtime: xParameter?.realtime ?? false,
      values: [],
    },
    yAxis: {
      name: yParameter?.name ?? "Y",
      realtime: yParameter?.realtime ?? false,
      values: [],
    },
    channels: [],
    repetitions: [],
    period: null,
  };
  if (parameters.length !== 2 || parameters.every((parameter) => parameter.realtime)) {
    return {
      ...base,
      error: "Heatmaps require two numeric scan axes, or one numeric axis and time.",
    };
  }
  if (
    repetition !== undefined &&
    (!Number.isSafeInteger(repetition) || repetition < 0)
  ) {
    return { ...base, error: "Invalid repetition." };
  }
  const period = parameters.some((parameter) => parameter.realtime)
    ? 0
    : xParameter.scan_values.length * yParameter.scan_values.length;
  base.period = Number.isSafeInteger(period) && period > 0 ? period : null;
  const [xMap, yMap] = resolveViewerScanMaps(data.scan_parameters, parameters);
  const xValues = new Set(
    xParameter.realtime ? [] : xParameter.scan_values.filter(Number.isFinite),
  );
  const yValues = new Set(
    yParameter.realtime ? [] : yParameter.scan_values.filter(Number.isFinite),
  );
  const repetitions = new Set<number>();
  const channels = data.device_data[0]?.readouts.result_channels ?? {};
  for (const name of [...new Set(channelNames)]) {
    const cells = new Map<string, HeatmapCell>();
    const entries = Object.entries(channels[name] ?? {}).sort(
      ([a], [b]) => Number(a) - Number(b),
    );
    for (const [indexKey, value] of entries) {
      const index = Number(indexKey);
      if (!Number.isSafeInteger(index) || index < 0 || !Number.isFinite(value))
        continue;
      const x = coordinate(xMap[indexKey], xParameter.realtime);
      const y = coordinate(yMap[indexKey], yParameter.realtime);
      if (x === null || y === null) continue;
      xValues.add(x);
      yValues.add(y);
      const ordinal = base.period ? Math.floor(index / base.period) : 0;
      repetitions.add(ordinal);
      if (repetition !== undefined && ordinal !== repetition) continue;
      const key = JSON.stringify([x, y]);
      const existing = cells.get(key);
      if (existing) {
        const count = existing.count + 1;
        // Weighted mean avoids overflowing a sum for otherwise finite observations.
        existing.value = existing.value * (existing.count / count) + value / count;
        existing.count = count;
        existing.pointIndices.push(index);
      } else {
        cells.set(key, { x, y, value, count: 1, pointIndices: [index] });
      }
    }
    const observed = [...cells.values()].sort((a, b) => a.x - b.x || a.y - b.y);
    base.channels.push({ name, cells: observed, ...heatmapValueRange(observed) });
  }
  base.xAxis.values = [...xValues].sort((a, b) => a - b);
  base.yAxis.values = [...yValues].sort((a, b) => a - b);
  base.repetitions = [...repetitions].sort((a, b) => a - b);
  return base;
}

/** Stable numeric/ISO category labels also let the viewer translate manual axis bounds. */
export function heatmapAxisCategories(axis: HeatmapAxis): string[] {
  return axis.values.map((value) =>
    axis.realtime ? new Date(value).toISOString() : String(value),
  );
}

export function heatmapSeriesData(
  channel: HeatmapChannel,
  xAxis: HeatmapAxis,
  yAxis: HeatmapAxis,
): [number, number, number, number][] {
  const xIndices = new Map(xAxis.values.map((value, index) => [value, index]));
  const yIndices = new Map(yAxis.values.map((value, index) => [value, index]));
  return channel.cells.flatMap((cell) => {
    const x = xIndices.get(cell.x);
    const y = yIndices.get(cell.y);
    return x === undefined || y === undefined ? [] : [[x, y, cell.value, cell.count]];
  });
}
