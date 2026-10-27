import {
  averageRepeatedPlot,
  hasFittablePoints,
  hasNumericScanAxis,
  observedScanParameters,
  plotViewerUrl,
  projectPlotData,
  selectPlot,
} from "../../../src/features/plot-viewer/plotSelection";
import type {
  ExperimentDataPayload as ExperimentData,
  ExperimentDeviceData,
} from "../../../src/types/ExperimentData";
import type { ScanParameter } from "../../../src/types/ScanParameter";

const device: ExperimentDeviceData<Record<string, number[]>> = {
  device_id: "second/device",
  readouts: {
    result_channels: {
      A: { 100: 1, 102: 3 },
      B: { 101: 2, 102: 4 },
      other: { 100: 20 },
    },
    shot_channels: {},
  },
  plot_windows: {
    result_channels: [
      { name: "Selected", index: 7, type: "readout", channel_names: ["A", "B"] },
    ],
    shot_channels: [],
  },
  fits: {},
};
const data: ExperimentData = {
  device_data: [{ ...device, device_id: "first" }, device],
  scan_parameters: {
    timestamp: { 100: "t100", 101: "t101", 102: "t102" },
    x: { 100: 10, 101: 11, 102: 12 },
  },
  parameters: {},
  total_data_points: 103,
};

test("selects the route device and metadata index, never an array offset or another device", () => {
  expect(selectPlot(data, "second/device", "readout", "7")?.device).toBe(device);
  expect(selectPlot(data, "missing", "readout", "7")).toBeNull();
  expect(selectPlot(data, "second/device", "readout", "0")).toBeNull();
  expect(selectPlot(data, null, "readout", "7abc")).toBeNull();
  expect(plotViewerUrl("2", "readout", 7, "second/device")).toBe(
    "/data/2/plot/readout/7?device=second%2Fdevice",
  );
});

test("aligns sparse channels on original scan indices without mutating the held snapshot", () => {
  const result = projectPlotData(data, device, ["A", "B"]);
  expect(result.device_data).toHaveLength(1);
  expect(Object.keys(result.device_data[0].readouts.result_channels)).toEqual([
    "A",
    "B",
  ]);
  expect(Object.values(result.device_data[0].readouts.result_channels.A)).toEqual([
    1,
    NaN,
    3,
  ]);
  expect(Object.values(result.device_data[0].readouts.result_channels.B)).toEqual([
    NaN,
    2,
    4,
  ]);
  expect(Object.values(result.scan_parameters.x)).toEqual([10, 11, 12]);
  expect(device.readouts.result_channels.A).toEqual({ 100: 1, 102: 3 });
});

test("omits a point whose scan coordinates are missing and uses observed X for a retained finite tail", () => {
  const sparse = {
    ...data,
    scan_parameters: { ...data.scan_parameters, x: { 101: 11, 102: 12 } },
  };
  const result = projectPlotData(sparse, device, ["A", "B"]);
  expect(Object.keys(result.device_data[0].readouts.result_channels.A)).toEqual([
    "101",
    "102",
  ]);
  const parameter = { scan_values: [0, 1, 2], realtime: false } as ScanParameter;
  expect(observedScanParameters(result, [parameter])[0].scan_values).toEqual([11, 12]);
  expect(parameter.scan_values).toEqual([0, 1, 2]);
});

test("does not reinterpret strings or booleans as numeric scan coordinates", () => {
  for (const value of [true, "12", Number.NaN]) {
    const nonnumeric = {
      ...data,
      scan_parameters: { x: { 100: value, 101: value, 102: value } },
    };
    expect(hasNumericScanAxis(nonnumeric)).toBe(false);
    expect(hasFittablePoints(nonnumeric)).toBe(false);
  }
  expect(hasFittablePoints(projectPlotData(data, device, ["A"]))).toBe(false);
});

test("averages repeated samples by original scan position even when earlier repetitions were omitted", () => {
  const repeated = {
    ...data,
    scan_parameters: { x: { 7: 10, 8: 20, 9: 0, 10: 10, 11: 20 } },
    device_data: [
      {
        ...device,
        readouts: {
          ...device.readouts,
          result_channels: { A: { 7: 2, 8: 4, 9: 6, 10: 8, 11: 10 } },
        },
      },
    ],
  };
  const parameters = [{ scan_values: [0, 10, 20], realtime: false } as ScanParameter];
  const averaged = averageRepeatedPlot(repeated, parameters, 4);
  expect(Object.values(averaged.device_data[0].readouts.result_channels.A)).toEqual([
    6, 5, 7,
  ]);
  expect(observedScanParameters(averaged, parameters)[0].scan_values).toEqual([
    0, 10, 20,
  ]);
  expect(Object.keys(repeated.device_data[0].readouts.result_channels.A)).toHaveLength(
    5,
  );
});
