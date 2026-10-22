import { repetitionSeries } from "../../../src/features/plot-viewer/repetitionSeries";
import type { ExperimentData } from "../../../src/types/ExperimentData";
import type { ScanParameter } from "../../../src/types/ScanParameter";
const parameter: ScanParameter = {
  id: 1,
  job_id: 1,
  name: "x",
  variable_id: "x",
  realtime: false,
  scan_values: [-1, 0, 1],
};
const data = {
  scan_parameters: { x: { "1": 0, "2": 1, "3": -1, "5": 1 } },
  device_data: [
    {
      readouts: { result_channels: { count: { "1": 10, "2": 20, "3": 30, "5": 50 } } },
    },
  ],
} as unknown as ExperimentData;
test("truncated and sparse repetitions keep their original repetition number and X coordinate", () => {
  const series = repetitionSeries(data, parameter, 3);
  expect(series.map((s) => s.name)).toEqual(["count (rep 1)", "count (rep 2)"]);
  expect(series[0].data).toEqual([
    [-1, NaN],
    [0, 10],
    [1, 20],
  ]);
  expect(series[1].data).toEqual([
    [-1, 30],
    [0, NaN],
    [1, 50],
  ]);
});
test("last N scan positions apply equally to each individual repetition", () => {
  const series = repetitionSeries(data, parameter, 2);
  expect(series[0].data).toEqual([
    [0, 10],
    [1, 20],
  ]);
  expect(series[1].data).toEqual([
    [0, NaN],
    [1, 50],
  ]);
});
test("time scans do not invent finite raster repetitions", () => {
  expect(repetitionSeries(data, { ...parameter, realtime: true }, 10)).toEqual([]);
});
