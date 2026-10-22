import type { ExperimentData } from "../../../src/types/ExperimentData";
import type { ScanParameter } from "../../../src/types/ScanParameter";
import {
  buildHeatmapData,
  heatmapAxisCategories,
  heatmapSeriesData,
  heatmapValueRange,
} from "../../../src/features/plot-viewer/heatmapData";

const parameters: ScanParameter[] = [
  {
    id: 1,
    job_id: 1,
    name: "X axis",
    variable_id: "x",
    scan_values: [0, 10, 50],
    realtime: false,
  },
  {
    id: 2,
    job_id: 1,
    name: "Y axis",
    variable_id: "y",
    scan_values: [-1, 7],
    realtime: false,
  },
];
interface Point {
  index: number;
  x?: number;
  y?: number;
  a?: number;
  b?: number;
  timestamp?: string;
}
function fixture(points: Point[]): ExperimentData {
  const map = (field: keyof Point) =>
    Object.fromEntries(
      points
        .filter((point) => point[field] !== undefined)
        .map((point) => [point.index, point[field]]),
    );
  return {
    device_data: [
      {
        device_id: "d",
        fits: {},
        plot_windows: { result_channels: [], vector_channels: [], shot_channels: [] },
        readouts: {
          result_channels: {
            a: map("a") as Record<string, number>,
            b: map("b") as Record<string, number>,
          },
          vector_channels: {},
          shot_channels: {},
        },
      },
    ],
    scan_parameters: {
      x: map("x") as Record<string, number>,
      y: map("y") as Record<string, number>,
      timestamp: map("timestamp") as Record<string, string>,
    },
    parameters: {},
    total_data_points: Math.max(0, ...points.map((point) => point.index + 1)),
  };
}
function freeze(value: unknown): void {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
}

describe("indexed 2D heatmap data", () => {
  it("joins sparse out-of-order observations by original index and leaves missing cells blank", () => {
    const original = fixture([
      { index: 8, x: 50, y: 7, a: 80 },
      { index: 2, x: 10, y: -1, a: 20 },
      { index: 4, x: 50, y: -1, a: 40 },
      { index: 7, x: 0, y: 7, a: 70 },
      { index: 9, x: 50, a: 90 },
      { index: 12, y: 7, a: 120 },
      { index: 13, x: 10, y: 7, a: NaN },
    ]);
    freeze(original);
    const model = buildHeatmapData(original, parameters, ["a"]);
    expect(model.xAxis.values).toEqual([0, 10, 50]);
    expect(model.yAxis.values).toEqual([-1, 7]);
    expect(
      model.channels[0].cells.map(({ x, y, value, pointIndices }) => [
        x,
        y,
        value,
        pointIndices,
      ]),
    ).toEqual([
      [0, 7, 70, [7]],
      [10, -1, 20, [2]],
      [50, -1, 40, [4]],
      [50, 7, 80, [8]],
    ]);
    expect(heatmapSeriesData(model.channels[0], model.xAxis, model.yAxis)).toEqual([
      [0, 1, 70, 1],
      [1, 0, 20, 1],
      [2, 0, 40, 1],
      [2, 1, 80, 1],
    ]);
    // Index 8's observed (50, 7) differs from its planned raster position (10, -1).
    expect(model.channels[0].cells.at(-1)?.value).toBe(80);
  });

  it("keeps all planned numeric categories on a truncated grid and unions new observed values", () => {
    const model = buildHeatmapData(
      fixture([{ index: 100, x: 99, y: 7, a: 8 }]),
      parameters,
      ["a"],
    );
    expect(heatmapAxisCategories(model.xAxis)).toEqual(["0", "10", "50", "99"]);
    expect(model.yAxis.values).toEqual([-1, 7]);
    expect(heatmapSeriesData(model.channels[0], model.xAxis, model.yAxis)).toEqual([
      [3, 1, 8, 1],
    ]);
    expect(model.channels[0].cells).toHaveLength(1);
  });

  it("averages repeated observed cells and selects full raster passes from original indices", () => {
    const data = fixture([
      { index: 14, x: 50, y: 7, a: 30 },
      { index: 8, x: 50, y: 7, a: 10 },
      { index: 13, x: 0, y: 7, a: 50 },
    ]);
    const average = buildHeatmapData(data, parameters, ["a"]);
    expect(average.period).toBe(6);
    expect(average.repetitions).toEqual([1, 2]);
    expect(average.channels[0].cells.find((cell) => cell.x === 50)).toMatchObject({
      value: 20,
      count: 2,
      pointIndices: [8, 14],
    });
    const firstAvailable = buildHeatmapData(data, parameters, ["a"], 1);
    expect(firstAvailable.repetitions).toEqual([1, 2]);
    expect(firstAvailable.channels[0].cells).toEqual([
      { x: 50, y: 7, value: 10, count: 1, pointIndices: [8] },
    ]);
    expect(
      buildHeatmapData(data, parameters, ["a"], 2).channels[0].cells.map(
        (cell) => cell.value,
      ),
    ).toEqual([50, 30]);
    expect(buildHeatmapData(data, parameters, ["a"], 0).channels[0].cells).toEqual([]);
  });

  it("keeps per-channel missing cells and color ranges independent", () => {
    const model = buildHeatmapData(
      fixture([
        { index: 0, x: 0, y: -1, a: 10, b: -50 },
        { index: 1, x: 0, y: 7, a: 30 },
        { index: 2, x: 10, y: -1, b: -5 },
      ]),
      parameters,
      ["a", "b"],
    );
    expect(model.channels[0]).toMatchObject({ min: 10, max: 30 });
    expect(model.channels[1]).toMatchObject({ min: -50, max: -5 });
    expect(model.channels[0].cells.map((cell) => cell.pointIndices)).toEqual([
      [0],
      [1],
    ]);
    expect(model.channels[1].cells.map((cell) => cell.pointIndices)).toEqual([
      [0],
      [2],
    ]);
  });

  it("colors repeated means using averaged cell values rather than raw extrema", () => {
    const model = buildHeatmapData(
      fixture([
        { index: 0, x: 0, y: -1, a: 0 },
        { index: 6, x: 0, y: -1, a: 100 },
        { index: 1, x: 0, y: 7, a: 60 },
      ]),
      parameters,
      ["a"],
    );
    expect(model.channels[0]).toMatchObject({ min: 50, max: 60 });
  });

  it("maps time plus numeric scans using observed timestamps with chronological ISO categories", () => {
    const timeParameters = [
      {
        ...parameters[0],
        realtime: true,
        scan_values: [],
        variable_id: "Real Time",
        name: "Time",
      },
      parameters[1],
    ];
    const data = fixture([
      { index: 10, y: 7, a: 9, timestamp: "2026-10-22T12:00:02Z" },
      { index: 15, y: -1, a: 3, timestamp: "2026-10-22T12:00:00Z" },
      { index: 16, y: -1, a: 40, timestamp: "invalid" },
    ]);
    const model = buildHeatmapData(data, timeParameters, ["a"]);
    expect(model.period).toBeNull();
    expect(heatmapAxisCategories(model.xAxis)).toEqual([
      "2026-10-22T12:00:00.000Z",
      "2026-10-22T12:00:02.000Z",
    ]);
    expect(heatmapSeriesData(model.channels[0], model.xAxis, model.yAxis)).toEqual([
      [0, 0, 3, 1],
      [1, 1, 9, 1],
    ]);
    const yTime = buildHeatmapData(data, [parameters[1], timeParameters[0]], ["a"]);
    expect(yTime.yAxis.realtime).toBe(true);
    expect(heatmapSeriesData(yTime.channels[0], yTime.xAxis, yTime.yAxis)).toEqual([
      [0, 0, 3, 1],
      [1, 1, 9, 1],
    ]);
  });

  it("uses exact variable IDs first and exact display names as a compatibility fallback", () => {
    const data = fixture([{ index: 0, x: 50, y: -1, a: 7 }]);
    data.scan_parameters["X axis"] = { 0: 999 };
    expect(buildHeatmapData(data, parameters, ["a"]).channels[0].cells[0].x).toBe(50);
    delete data.scan_parameters.x;
    expect(buildHeatmapData(data, parameters, ["a"]).channels[0].cells[0].x).toBe(999);
  });

  it("returns planned blank axes for absent metadata and rejects unsupported scans/repetitions", () => {
    const data = fixture([]);
    expect(buildHeatmapData(data, parameters, ["a"]).channels[0].cells).toEqual([]);
    expect(buildHeatmapData(data, parameters, ["a"]).xAxis.values).toEqual([0, 10, 50]);
    expect(buildHeatmapData(data, [parameters[0]], ["a"]).error).toMatch(/two numeric/);
    expect(
      buildHeatmapData(
        data,
        parameters.map((parameter) => ({ ...parameter, realtime: true })),
        ["a"],
      ).error,
    ).toMatch(/two numeric/);
    expect(buildHeatmapData(data, parameters, ["a"], -1).error).toMatch(/repetition/);
  });

  it("provides finite color domains for empty, flat, and very large finite cell values", () => {
    expect(heatmapValueRange([])).toEqual({ min: 0, max: 1 });
    const cell = { x: 0, y: 0, value: 7, count: 1, pointIndices: [0] };
    expect(heatmapValueRange([cell])).toEqual({ min: 7, max: 8 });
    const range = heatmapValueRange([{ ...cell, value: Number.MAX_VALUE }]);
    expect(Number.isFinite(range.min) && Number.isFinite(range.max)).toBe(true);
    expect(range.max).toBeGreaterThan(range.min);
  });
});
