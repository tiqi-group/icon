import type { ExperimentDataPoint } from "../../../src/types/ExperimentData";
import type { ScanParameter } from "../../../src/types/ScanParameter";
import {
  applyPlotViewerUpdate,
  bufferPlotViewerUpdate,
  createPlotViewerBuffer,
  EMPTY_PLOT_VIEWER_DATA,
  replayPlotViewerBuffer,
} from "../../../src/features/plot-viewer/plotViewerData";
import type { PlotViewerData } from "../../../src/features/plot-viewer/plotViewerData";
import { projectPlotData } from "../../../src/features/plot-viewer/plotSelection";
import { buildHeatmapData } from "../../../src/features/plot-viewer/heatmapData";
import { resolveViewerScanMaps } from "../../../src/features/plot-viewer/viewerScanParameters";

const position = "position";
const frequency = "FREQUENCY";
const parameters: ScanParameter[] = [
  {
    id: 1,
    job_id: 1,
    variable_id: position,
    name: position,
    scan_values: [1, 2, 3],
    realtime: false,
    device_id: 3,
    device: { id: 3, name: "scanner-a" },
  },
  {
    id: 2,
    job_id: 1,
    variable_id: frequency,
    name: frequency,
    scan_values: [10, 20],
    realtime: false,
    device_id: null,
    device: null,
  },
];
function point(index: number): ExperimentDataPoint {
  return {
    index,
    scan_params: { [`Device(scanner-a) ${position}`]: 2.5, [frequency]: 17 },
    timestamp: `2026-10-27T12:00:${String(index % 60).padStart(2, "0")}Z`,
    device_data: [
      {
        device_id: "readout",
        hardware_instructions: "",
        readouts: {
          result_channels: { counts: index },
          shot_channels: {},
          vector_channels: {},
        },
      },
    ],
  };
}
function snapshot(count: number): PlotViewerData {
  const map = <T>(value: (index: number) => T) =>
    Object.fromEntries(
      Array.from({ length: count }, (_, index) => [index, value(index)]),
    );
  return {
    realtime_scan: false,
    total_data_points: count,
    parameters: {},
    scan_parameters: {
      timestamp: map((index) => point(index).timestamp),
      [position]: map(() => 1.5),
      [frequency]: map(() => 12),
    },
    device_data: [
      {
        device_id: "readout",
        fits: {},
        plot_windows: { result_channels: [], shot_channels: [] },
        readouts: {
          result_channels: { counts: map((index) => index) },
          shot_channels: {},
        },
      },
    ],
  };
}
function project(data: PlotViewerData, axes = parameters) {
  return projectPlotData(data, data.device_data[0], ["counts"], axes);
}
function freeze(value: unknown): void {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
}

it("keeps all 420 snapshot samples plus a device-qualified live point and observed 2D coordinates", () => {
  const held = snapshot(420);
  freeze(held);
  const heldPlot = project(held);
  const live = applyPlotViewerUpdate(held, { type: "point", value: point(420) });
  const plotted = project(live);
  expect(
    Object.keys(plotted.device_data[0].readouts.result_channels.counts),
  ).toHaveLength(421);
  expect(plotted.scan_parameters[position][420]).toBe(2.5);
  expect(Object.keys(plotted.scan_parameters)).toEqual([
    "timestamp",
    position,
    frequency,
  ]);
  const cells = buildHeatmapData(plotted, parameters, ["counts"]).channels[0].cells;
  expect(cells.find((cell) => cell.pointIndices.includes(420))).toMatchObject({
    x: 2.5,
    y: 17,
    value: 420,
  });
  // The acquired coordinates differ from every planned raster coordinate.
  expect(buildHeatmapData(live, parameters, ["counts"]).channels[0].cells).toEqual(
    cells,
  );
  expect(
    Object.keys(heldPlot.device_data[0].readouts.result_channels.counts),
  ).toHaveLength(420);
  expect(held.scan_parameters[`Device(scanner-a) ${position}`]).toBeUndefined();
});

it("reconciles events buffered before job metadata/snapshot arrival and fresh reconnect replay", () => {
  let buffer = createPlotViewerBuffer(false);
  for (const index of [419, 420])
    buffer = bufferPlotViewerUpdate(buffer, { type: "point", value: point(index) });
  const replayed = replayPlotViewerBuffer(snapshot(420), buffer);
  expect(
    Object.keys(project(replayed).device_data[0].readouts.result_channels.counts),
  ).toHaveLength(421);
  expect(project(replayed).scan_parameters[position][419]).toBe(2.5);
  let reconnect = createPlotViewerBuffer(false);
  reconnect = bufferPlotViewerUpdate(reconnect, { type: "point", value: point(421) });
  const refreshed = replayPlotViewerBuffer(snapshot(421), reconnect);
  expect(
    Object.keys(project(refreshed).device_data[0].readouts.result_channels.counts),
  ).toHaveLength(422);
  expect(project(refreshed).scan_parameters[position][421]).toBe(2.5);
});

it("renders live-only data after a snapshot failure once job metadata becomes available", () => {
  const live = applyPlotViewerUpdate(EMPTY_PLOT_VIEWER_DATA, {
    type: "point",
    value: point(8),
  });
  freeze(live);
  expect(project(live).scan_parameters[position]).toEqual({ 8: 2.5 });
  expect(
    buildHeatmapData(project(live), parameters, ["counts"]).channels[0].cells,
  ).toEqual([{ x: 2.5, y: 17, value: 8, count: 1, pointIndices: [8] }]);
});

it("does not assign an ambiguous unqualified snapshot axis to either device", () => {
  const axes = [
    parameters[0],
    { ...parameters[0], id: 3, device_id: 4, device: { id: 4, name: "scanner-b" } },
  ];
  const maps = {
    [position]: { 0: 99 },
    [`Device(scanner-a) ${position}`]: { 1: 2 },
    [`Device(scanner-b) ${position}`]: { 1: 3 },
  };
  expect(resolveViewerScanMaps(maps, axes)).toEqual([{ 1: 2 }, { 1: 3 }]);
  const data = snapshot(2);
  data.scan_parameters = maps;
  const plotted = project(data, axes);
  expect(Object.keys(plotted.device_data[0].readouts.result_channels.counts)).toEqual([
    "1",
  ]);
  expect(buildHeatmapData(plotted, axes, ["counts"]).channels[0].cells).toEqual([
    { x: 2, y: 3, value: 1, count: 1, pointIndices: [1] },
  ]);
  const sameDeviceName = [
    axes[0],
    { ...axes[1], device: { id: 4, name: "scanner-a" } },
  ];
  expect(resolveViewerScanMaps(maps, sameDeviceName)).toEqual([{}, {}]);
});

it("requires a known matching device identity and never strips arbitrary prefixes", () => {
  const maps = { [`Device(scanner-b) ${position}`]: { 0: 2 } };
  expect(resolveViewerScanMaps(maps, [parameters[0]])).toEqual([{}]);
  expect(
    resolveViewerScanMaps({ [`Device(scanner-a) ${position}`]: { 0: 2 } }, [
      { ...parameters[0], device_id: 999 },
    ]),
  ).toEqual([{}]);
  expect(
    resolveViewerScanMaps({ [`Device(scanner-a) ${position}`]: { 0: 2 } }, [
      { ...parameters[0], device: undefined },
    ]),
  ).toEqual([{}]);
});

it("preserves older unqualified metadata, display-name fallback and variable-ID priority", () => {
  const axis = {
    ...parameters[0],
    name: "Position",
    device_id: undefined,
    device: undefined,
  };
  expect(
    resolveViewerScanMaps({ [position]: { 0: 1 }, Position: { 0: 9 } }, [axis]),
  ).toEqual([{ 0: 1 }]);
  expect(resolveViewerScanMaps({ Position: { 0: 9 } }, [axis])).toEqual([{ 0: 9 }]);
  const data = snapshot(2);
  data.device_data[0].readouts.shot_channels.counts = { 1: [4, 5] };
  const projected = project(data, [axis]);
  expect(Object.keys(projected.device_data[0].readouts.result_channels.counts)).toEqual(
    ["0", "1"],
  );
  expect(projected.device_data[0].readouts.shot_channels.counts).toEqual([4, 5]);
});

it("uses timestamps for a realtime axis without interpreting a Real Time alias as a second axis", () => {
  const data = snapshot(2);
  data.scan_parameters["Real Time"] = { 0: 0 };
  const time = {
    ...parameters[0],
    realtime: true,
    variable_id: "Real Time",
    name: "Time",
    scan_values: [],
  };
  const projected = project(data, [time]);
  expect(Object.keys(projected.scan_parameters)).toEqual(["timestamp"]);
  expect(Object.keys(projected.device_data[0].readouts.result_channels.counts)).toEqual(
    ["0", "1"],
  );
});
