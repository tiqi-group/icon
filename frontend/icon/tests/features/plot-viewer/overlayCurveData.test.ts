import type { HeatmapData } from "../../../src/features/plot-viewer/heatmapData";
import { buildHeatmapData } from "../../../src/features/plot-viewer/heatmapData";
import {
  availableCurveSlices,
  buildOverlayCurves,
  curveSliceLabel,
} from "../../../src/features/plot-viewer/overlayCurveData";
import type { ExperimentData } from "../../../src/types/ExperimentData";
import type { ScanParameter } from "../../../src/types/ScanParameter";

function fixture(): HeatmapData {
  return {
    xAxis: { name: "Frequency", realtime: false, values: [0, 1, 10, 100] },
    yAxis: { name: "Power", realtime: false, values: [-30, 10, 20, 30] },
    channels: [
      {
        name: "counts",
        min: -5,
        max: 99,
        cells: [
          { x: 100, y: 20, value: 99, count: 3, pointIndices: [3, 7, 11] },
          { x: 10, y: 10, value: 8, count: 1, pointIndices: [2] },
          { x: 0, y: 10, value: -5, count: 2, pointIndices: [0, 4] },
        ],
      },
      {
        name: "other",
        min: 7,
        max: 8,
        cells: [{ x: 1, y: -30, value: 7, count: 1, pointIndices: [1] }],
      },
    ],
    repetitions: [0, 1, 2],
    period: 4,
  };
}
function freeze(value: unknown): void {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
}

describe("available overlay slices", () => {
  test("offers only observed values for the chosen channel and fixed axis", () => {
    const model = fixture();
    expect(availableCurveSlices(model, "counts", "x")).toEqual([10, 20]);
    expect(availableCurveSlices(model, "counts", "y")).toEqual([0, 10, 100]);
    expect(availableCurveSlices(model, "other", "x")).toEqual([-30]);
    expect(availableCurveSlices(model, "missing", "x")).toEqual([]);
  });

  test("empty and nonfinite observations cannot create available slices", () => {
    const model = fixture();
    model.channels[0].cells = [
      { x: 0, y: 10, value: NaN, count: 1, pointIndices: [0] },
      { x: Infinity, y: 20, value: 3, count: 1, pointIndices: [1] },
      { x: 1, y: 30, value: 7, count: 0, pointIndices: [] },
    ];
    expect(availableCurveSlices(model, "counts", "x")).toEqual([]);
  });
});

describe("true-coordinate overlaid curves", () => {
  test("retains uneven X and actual measured values on the same scale, with explicit null gaps", () => {
    const model = fixture();
    freeze(model);
    const curves = buildOverlayCurves(model, "counts", "x", [20, 10]);
    expect(curves.map((curve) => curve.fixedValue)).toEqual([10, 20]);
    expect(curves[0].points).toEqual([
      [0, -5, 2],
      [1, null, 0],
      [10, 8, 1],
      [100, null, 0],
    ]);
    expect(curves[1].points).toEqual([
      [0, null, 0],
      [100, 99, 3],
    ]);
    expect(curves[0].label).toBe("Power = 10");
    expect(curves[1].label).toBe("Power = 20");
    expect(curves[0].id).not.toBe(curves[1].id);
    expect(model.channels[0].cells[0].value).toBe(99);
  });

  test("swaps to true Y coordinates while preserving measured values", () => {
    const curves = buildOverlayCurves(fixture(), "counts", "y", [100, 0, 10]);
    expect(curves.map((curve) => curve.fixedValue)).toEqual([0, 10, 100]);
    expect(curves[0].points).toEqual([
      [-30, null, 0],
      [10, -5, 2],
      [30, null, 0],
    ]);
    expect(curves[1].points).toEqual([
      [-30, null, 0],
      [10, 8, 1],
      [30, null, 0],
    ]);
    expect(curves[2].points).toEqual([
      [-30, null, 0],
      [20, 99, 3],
      [30, null, 0],
    ]);
    expect(curves[0].label).toBe("Frequency = 0");
  });

  test("returns empty points for missing selected slices and safely handles empty selections", () => {
    const model = fixture();
    expect(buildOverlayCurves(model, "counts", "x", [30])[0].points).toEqual([]);
    expect(buildOverlayCurves(model, "counts", "x", [])).toEqual([]);
    expect(buildOverlayCurves(model, "missing", "x", [10])).toEqual([]);
    expect(buildOverlayCurves(model, "counts", "x", [NaN, Infinity])).toEqual([]);
    expect(buildOverlayCurves(model, "counts", "x", [10, 10])).toHaveLength(1);
  });

  test("stable IDs and labels preserve precise numeric fixed coordinates", () => {
    const model = fixture();
    const precise = 1.000000000000123;
    const selected = [precise, 10];
    const first = buildOverlayCurves(model, "counts", "x", selected);
    const second = buildOverlayCurves(model, "counts", "x", [...selected].reverse());
    expect(first.map((curve) => curve.id)).toEqual(second.map((curve) => curve.id));
    expect(curveSliceLabel(model, "x", precise)).toBe("Power = 1.000000000000123");
    expect(buildOverlayCurves(model, "other", "x", selected)[0].id).not.toBe(
      first[0].id,
    );
  });

  test("uses timestamp milliseconds horizontally and precise ISO labels for a fixed time axis", () => {
    const model = fixture();
    const start = Date.parse("2026-10-22T12:00:00.123Z");
    model.xAxis = {
      name: "Time",
      realtime: true,
      values: [start, start + 1, start + 2000],
    };
    model.channels[0].cells = [
      { x: start + 2000, y: 10, value: 4, count: 1, pointIndices: [2] },
      { x: start, y: 10, value: 2, count: 1, pointIndices: [0] },
    ];
    expect(buildOverlayCurves(model, "counts", "x", [10])[0].points).toEqual([
      [start, 2, 1],
      [start + 2000, 4, 1],
    ]);
    expect(availableCurveSlices(model, "counts", "y")).toEqual([start, start + 2000]);
    expect(curveSliceLabel(model, "y", start)).toBe("Time = 2026-10-22T12:00:00.123Z");
  });

  test("a missing horizontal coordinate in the axis metadata cannot relocate an observation", () => {
    const model = fixture();
    model.xAxis.values = [0, 1];
    model.channels[0].cells = [
      { x: 1.5, y: 10, value: 20, count: 1, pointIndices: [0] },
    ];
    expect(buildOverlayCurves(model, "counts", "x", [10])[0].points).toEqual([
      [0, null, 0],
      [1.5, 20, 1],
    ]);
  });

  test("large sparse grids produce bounded sentinel counts rather than a Cartesian expansion", () => {
    const model = fixture();
    model.xAxis.values = Array.from({ length: 100000 }, (_, index) => index);
    model.yAxis.values = Array.from({ length: 100000 }, (_, index) => index);
    model.channels[0].cells = [
      { x: 1, y: 2, value: 17, count: 1, pointIndices: [0] },
      { x: 99998, y: 7, value: 23, count: 1, pointIndices: [1] },
    ];
    expect(availableCurveSlices(model, "counts", "x")).toEqual([2, 7]);
    const curves = buildOverlayCurves(model, "counts", "x", [2, 7, 99999]);
    expect(curves.map((curve) => curve.points.length)).toEqual([3, 3, 0]);
    expect(curves[0].points).toEqual([
      [0, null, 0],
      [1, 17, 1],
      [99999, null, 0],
    ]);
  });
});

test("overlay curves consume averaged or individual repetition models without changing their values", () => {
  const parameters: ScanParameter[] = [
    {
      id: 1,
      job_id: 1,
      name: "X",
      variable_id: "x",
      scan_values: [0, 2, 9],
      realtime: false,
    },
    {
      id: 2,
      job_id: 1,
      name: "Y",
      variable_id: "y",
      scan_values: [1, 4],
      realtime: false,
    },
  ];
  const data: ExperimentData = {
    parameters: {},
    total_data_points: 9,
    scan_parameters: {
      x: { 0: 0, 1: 0, 2: 2, 4: 9, 6: 0, 7: 0, 8: 2 },
      y: { 0: 1, 1: 4, 2: 1, 4: 1, 6: 1, 7: 4, 8: 1 },
    },
    device_data: [
      {
        device_id: "d",
        fits: {},
        plot_windows: { result_channels: [], shot_channels: [] },
        readouts: {
          result_channels: { counts: { 0: 2, 1: 10, 2: 8, 4: 20, 6: 6, 7: 14, 8: 12 } },
          shot_channels: {},
        },
      },
    ],
  };
  const average = buildHeatmapData(data, parameters, ["counts"]);
  expect(buildOverlayCurves(average, "counts", "x", [1])[0].points).toEqual([
    [0, 4, 2],
    [2, 10, 2],
    [9, 20, 1],
  ]);
  const repetition = buildHeatmapData(data, parameters, ["counts"], 1);
  expect(buildOverlayCurves(repetition, "counts", "x", [1])[0].points).toEqual([
    [0, 6, 1],
    [2, 12, 1],
    [9, null, 0],
  ]);
});

test("slice IDs cannot collide when channel punctuation and negative coordinates overlap", () => {
  const model = fixture();
  model.channels.push({ name: "counts-", cells: [], min: 0, max: 1 });
  const negative = buildOverlayCurves(model, "counts", "x", [-2])[0];
  const positive = buildOverlayCurves(model, "counts-", "x", [2])[0];
  expect(negative.id).not.toBe(positive.id);
});

test("one sentinel breaks a long internal missing run, while measured zero remains zero", () => {
  const model = fixture();
  model.xAxis.values = Array.from({ length: 10000 }, (_, index) => index);
  model.channels[0].cells = [
    { x: 0, y: 10, value: 0, count: 1, pointIndices: [0] },
    { x: 9999, y: 10, value: 2, count: 1, pointIndices: [1] },
  ];
  expect(buildOverlayCurves(model, "counts", "x", [10])[0].points).toEqual([
    [0, 0, 1],
    [1, null, 0],
    [9999, 2, 1],
  ]);
});

test("interleaved realtime slices keep their own observations connected without inferred timestamp gaps", () => {
  const model = fixture();
  const start = Date.parse("2026-10-22T12:00:00Z");
  model.xAxis = {
    name: "Time",
    realtime: true,
    values: [start, start + 1, start + 2, start + 3],
  };
  model.channels[0].cells = [
    { x: start + 2, y: 10, value: 12, count: 2, pointIndices: [2] },
    { x: start, y: 10, value: 10, count: 1, pointIndices: [0] },
    { x: start + 3, y: 20, value: 23, count: 1, pointIndices: [3] },
    { x: start + 1, y: 20, value: 21, count: 1, pointIndices: [1] },
  ];
  const xTime = buildOverlayCurves(model, "counts", "x", [10, 20]);
  expect(xTime.map((curve) => curve.points)).toEqual([
    [
      [start, 10, 1],
      [start + 2, 12, 2],
    ],
    [
      [start + 1, 21, 1],
      [start + 3, 23, 1],
    ],
  ]);
  const swapped: HeatmapData = {
    ...model,
    xAxis: model.yAxis,
    yAxis: model.xAxis,
    channels: [
      {
        ...model.channels[0],
        cells: model.channels[0].cells.map((cell) => ({
          ...cell,
          x: cell.y,
          y: cell.x,
        })),
      },
    ],
  };
  expect(
    buildOverlayCurves(swapped, "counts", "y", [10, 20]).map((curve) => curve.points),
  ).toEqual(xTime.map((curve) => curve.points));
});
