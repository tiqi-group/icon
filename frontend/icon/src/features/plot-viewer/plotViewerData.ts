import type {
  ExperimentData,
  ExperimentDataPoint,
  ExperimentDeviceData,
  FitResult,
  ParameterValue,
  PlotWindows,
} from "../../types/ExperimentData";

export const LIVE_POINT_LIMIT = 2000;
export const MAX_LIVE_POINT_LIMIT = 100_000;

/** Invalid requests use the default; valid positive integer requests are capped. */
export function normalizePlotViewerLimit(requested = LIVE_POINT_LIMIT): number {
  return Number.isSafeInteger(requested) && requested > 0
    ? Math.min(requested, MAX_LIVE_POINT_LIMIT)
    : LIVE_POINT_LIMIT;
}
export type PlotViewerData = ExperimentData & { realtime_scan?: boolean };
export const EMPTY_PLOT_VIEWER_DATA: PlotViewerData = {
  device_data: [],
  scan_parameters: {},
  parameters: {},
  total_data_points: 0,
};

type FitUpdate =
  | { device_id: string; fit_data: FitResult }
  | { device_id: string; deleted: boolean; result_channel: string };
export type PlotViewerUpdate =
  | { type: "point"; value: ExperimentDataPoint }
  | {
      type: "metadata";
      value: { device_id: string; readout_metadata: PlotWindows }[];
    }
  | { type: "parameters"; value: Record<string, ParameterValue> }
  | { type: "fit"; value: FitUpdate };

function defaultDevice(deviceId: string): ExperimentDeviceData {
  return {
    device_id: deviceId,
    readouts: { result_channels: {}, vector_channels: {}, shot_channels: {} },
    plot_windows: { result_channels: [], vector_channels: [], shot_channels: [] },
    fits: {},
  };
}

function numericIndices(map: Record<string, unknown>): string[] {
  return Object.keys(map).filter(
    (key) => Number.isSafeInteger(Number(key)) && Number(key) >= 0,
  );
}

function latestArrays<T>(
  channels: Record<string, Record<string, T>>,
): Record<string, Record<string, T>> {
  return Object.fromEntries(
    Object.entries(channels).map(([channel, values]) => {
      const latest = numericIndices(values).sort((a, b) => Number(b) - Number(a))[0];
      return [channel, latest === undefined ? {} : { [latest]: values[latest] }];
    }),
  );
}

/** Keep original indices aligned; finite scans retain every available scalar point. */
export function retainPlotViewerData(
  data: PlotViewerData,
  requestedLimit = LIVE_POINT_LIMIT,
): PlotViewerData {
  const livePointLimit = normalizePlotViewerLimit(requestedLimit);
  const realtime =
    data.realtime_scan === true ||
    (data.realtime_scan === undefined &&
      ("Real Time" in data.scan_parameters ||
        // Pure realtime events contain no scan_params. Bound their time trace
        // even when the first snapshot failed before realtime metadata arrived.
        ("timestamp" in data.scan_parameters &&
          Object.keys(data.scan_parameters).every((name) => name === "timestamp"))));
  let keep: Set<string> | undefined;
  if (realtime) {
    const indices = new Set<string>();
    for (const sequence of Object.values(data.scan_parameters)) {
      numericIndices(sequence).forEach((index) => indices.add(index));
    }
    for (const device of data.device_data) {
      for (const sequence of Object.values(device.readouts.result_channels)) {
        numericIndices(sequence).forEach((index) => indices.add(index));
      }
    }
    keep = new Set(
      [...indices].sort((a, b) => Number(b) - Number(a)).slice(0, livePointLimit),
    );
  }
  const retain = <T>(values: Record<string, T>): Record<string, T> =>
    keep
      ? Object.fromEntries(Object.entries(values).filter(([index]) => keep?.has(index)))
      : values;
  return {
    ...data,
    scan_parameters: Object.fromEntries(
      Object.entries(data.scan_parameters).map(([name, values]) => [
        name,
        retain(values),
      ]),
    ),
    device_data: data.device_data.map((device) => ({
      ...device,
      readouts: {
        result_channels: Object.fromEntries(
          Object.entries(device.readouts.result_channels).map(([channel, values]) => [
            channel,
            retain(values),
          ]),
        ),
        shot_channels: latestArrays(device.readouts.shot_channels),
        vector_channels: latestArrays(device.readouts.vector_channels),
      },
    })),
  };
}

function mergeSequences<T>(
  previous: Record<string, Record<string, T>>,
  additions: Record<string, Record<string, T>>,
): Record<string, Record<string, T>> {
  const merged = { ...previous };
  for (const [channel, values] of Object.entries(additions)) {
    merged[channel] = { ...previous[channel], ...values };
  }
  return merged;
}

export function applyPlotViewerUpdate(
  previous: PlotViewerData,
  update: PlotViewerUpdate,
  livePointLimit = LIVE_POINT_LIMIT,
): PlotViewerData {
  if (update.type === "parameters") {
    return { ...previous, parameters: { ...previous.parameters, ...update.value } };
  }
  const devices = new Map(
    previous.device_data.map((device) => [device.device_id, device]),
  );
  if (update.type === "metadata") {
    for (const item of update.value) {
      const device = devices.get(item.device_id) ?? defaultDevice(item.device_id);
      devices.set(item.device_id, { ...device, plot_windows: item.readout_metadata });
    }
    return { ...previous, device_data: [...devices.values()] };
  }
  if (update.type === "fit") {
    const value = update.value;
    const device = devices.get(value.device_id) ?? defaultDevice(value.device_id);
    const fits = { ...device.fits };
    if ("deleted" in value) delete fits[value.result_channel];
    else fits[value.fit_data.result_channel] = value.fit_data;
    devices.set(value.device_id, { ...device, fits });
    return { ...previous, device_data: [...devices.values()] };
  }
  const point = update.value;
  if (!Number.isSafeInteger(point.index) || point.index < 0)
    throw new Error("Invalid experiment point index");
  const scanParameters = { ...previous.scan_parameters };
  for (const [name, value] of Object.entries({
    ...point.scan_params,
    timestamp: point.timestamp,
  })) {
    scanParameters[name] = { ...previous.scan_parameters[name], [point.index]: value };
  }
  for (const item of point.device_data) {
    const device = devices.get(item.device_id) ?? defaultDevice(item.device_id);
    const atIndex = <T>(values: Record<string, T>) =>
      Object.fromEntries(
        Object.entries(values).map(([channel, value]) => [
          channel,
          { [point.index]: value },
        ]),
      );
    devices.set(item.device_id, {
      ...device,
      readouts: {
        result_channels: mergeSequences(
          device.readouts.result_channels,
          atIndex(item.readouts.result_channels),
        ),
        shot_channels: mergeSequences(
          device.readouts.shot_channels,
          atIndex(item.readouts.shot_channels),
        ),
        vector_channels: mergeSequences(
          device.readouts.vector_channels,
          atIndex(item.readouts.vector_channels),
        ),
      },
    });
  }
  return retainPlotViewerData(
    {
      ...previous,
      scan_parameters: scanParameters,
      device_data: [...devices.values()],
      total_data_points: Math.max(previous.total_data_points, point.index + 1),
    },
    livePointLimit,
  );
}

/** Compact updates during an RPC into maps, including fit tombstones for replay. */
export interface PlotViewerBuffer {
  data: PlotViewerData;
  metadataDevices: Set<string>;
  fitUpdates: Record<string, Record<string, FitResult | null>>;
}

export function createPlotViewerBuffer(realtime?: boolean): PlotViewerBuffer {
  return {
    data: { ...EMPTY_PLOT_VIEWER_DATA, realtime_scan: realtime },
    metadataDevices: new Set(),
    fitUpdates: {},
  };
}

export function bufferPlotViewerUpdate(
  buffer: PlotViewerBuffer,
  update: PlotViewerUpdate,
  livePointLimit = LIVE_POINT_LIMIT,
): PlotViewerBuffer {
  const next = {
    ...buffer,
    data: applyPlotViewerUpdate(buffer.data, update, livePointLimit),
  };
  if (update.type === "metadata") {
    next.metadataDevices = new Set([
      ...buffer.metadataDevices,
      ...update.value.map((item) => item.device_id),
    ]);
  }
  if (update.type === "fit") {
    const value = update.value;
    const channel =
      "deleted" in value ? value.result_channel : value.fit_data.result_channel;
    next.fitUpdates = {
      ...buffer.fitUpdates,
      [value.device_id]: {
        ...buffer.fitUpdates[value.device_id],
        [channel]: "deleted" in value ? null : value.fit_data,
      },
    };
  }
  return next;
}

export function replayPlotViewerBuffer(
  snapshot: PlotViewerData,
  buffer: PlotViewerBuffer,
  livePointLimit = LIVE_POINT_LIMIT,
): PlotViewerData {
  const devices = new Map(
    snapshot.device_data.map((device) => [device.device_id, device]),
  );
  for (const addition of buffer.data.device_data) {
    const previous =
      devices.get(addition.device_id) ?? defaultDevice(addition.device_id);
    const fits = { ...previous.fits };
    for (const [channel, fit] of Object.entries(
      buffer.fitUpdates[addition.device_id] ?? {},
    )) {
      if (fit === null) delete fits[channel];
      else fits[channel] = fit;
    }
    devices.set(addition.device_id, {
      ...previous,
      plot_windows: buffer.metadataDevices.has(addition.device_id)
        ? addition.plot_windows
        : previous.plot_windows,
      fits,
      readouts: {
        result_channels: mergeSequences(
          previous.readouts.result_channels,
          addition.readouts.result_channels,
        ),
        shot_channels: mergeSequences(
          previous.readouts.shot_channels,
          addition.readouts.shot_channels,
        ),
        vector_channels: mergeSequences(
          previous.readouts.vector_channels,
          addition.readouts.vector_channels,
        ),
      },
    });
  }
  return retainPlotViewerData(
    {
      ...snapshot,
      device_data: [...devices.values()],
      scan_parameters: mergeSequences(
        snapshot.scan_parameters,
        buffer.data.scan_parameters,
      ),
      parameters: { ...snapshot.parameters, ...buffer.data.parameters },
      total_data_points: Math.max(
        snapshot.total_data_points,
        buffer.data.total_data_points,
      ),
    },
    livePointLimit,
  );
}

export function validatePlotViewerSnapshot(
  value: unknown,
  livePointLimit = LIVE_POINT_LIMIT,
): PlotViewerData {
  if (!value || typeof value !== "object")
    throw new Error("Invalid experiment snapshot");
  const data = value as PlotViewerData;
  if (
    !Array.isArray(data.device_data) ||
    !data.scan_parameters ||
    !data.parameters ||
    !Number.isSafeInteger(data.total_data_points) ||
    data.total_data_points < 0
  ) {
    throw new Error("Invalid experiment snapshot");
  }
  // Retention also checks nested sequence structure before the good snapshot is replaced.
  return retainPlotViewerData(data, livePointLimit);
}
