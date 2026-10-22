import type { ExperimentDataPoint, FitResult } from "../../../src/types/ExperimentData";
import {
  applyPlotViewerUpdate,
  bufferPlotViewerUpdate,
  createPlotViewerBuffer,
  EMPTY_PLOT_VIEWER_DATA,
  LIVE_POINT_LIMIT,
  MAX_LIVE_POINT_LIMIT,
  normalizePlotViewerLimit,
  replayPlotViewerBuffer,
  retainPlotViewerData,
  validatePlotViewerSnapshot,
} from "../../../src/features/plot-viewer/plotViewerData";
import type { PlotViewerData } from "../../../src/features/plot-viewer/plotViewerData";

const point = (index: number, value = index): ExperimentDataPoint => ({
  index,
  scan_params: { x: value },
  timestamp: String(index),
  device_data: [
    {
      device_id: "d",
      hardware_instructions: "not retained",
      readouts: {
        result_channels: { a: value },
        shot_channels: { h: [value] },
        vector_channels: { v: [value, value + 1] },
      },
    },
  ],
});
function snapshot(count: number, realtime = false): PlotViewerData {
  const values = Object.fromEntries(
    Array.from({ length: count }, (_, index) => [index, index]),
  );
  return {
    realtime_scan: realtime,
    device_data: [
      {
        device_id: "d",
        readouts: {
          result_channels: { a: values, b: { ...values } },
          shot_channels: { h: { 0: [1], [count - 1]: [2] } },
          vector_channels: { v: { 0: [3], [count - 1]: [4] } },
        },
        plot_windows: { result_channels: [], vector_channels: [], shot_channels: [] },
        fits: {},
      },
    ],
    scan_parameters: { x: { ...values }, timestamp: { ...values } },
    parameters: {},
    total_data_points: count,
  };
}
const fit: FitResult = {
  result_channel: "a",
  func_type: "linear",
  x_range: null,
  init: {},
  result: { a: 1 },
  goodness: {},
  success: true,
  message: "",
};
function freezeDeep(value: unknown): void {
  if (value && typeof value === "object") {
    Object.values(value).forEach(freezeDeep);
    Object.freeze(value);
  }
}

describe("viewer retention and immutable updates", () => {
  it("retains the same latest numeric indices across realtime scans and scalar channels", () => {
    const original = snapshot(2007, true);
    original.device_data.push({ ...original.device_data[0], device_id: "other" });
    freezeDeep(original);
    const retained = retainPlotViewerData(original);
    expect(Object.keys(retained.scan_parameters.x)).toHaveLength(LIVE_POINT_LIMIT);
    expect(Object.keys(retained.scan_parameters.x)[0]).toBe("7");
    expect(Object.keys(retained.scan_parameters.timestamp)).toEqual(
      Object.keys(retained.scan_parameters.x),
    );
    for (const device of retained.device_data) {
      for (const sequence of Object.values(device.readouts.result_channels)) {
        expect(Object.keys(sequence)).toEqual(Object.keys(retained.scan_parameters.x));
      }
    }
    expect(original.scan_parameters.x[0]).toBe(0);
    expect(Object.keys(original.scan_parameters.x)).toHaveLength(2007);
  });

  it("keeps an available finite snapshot larger than the live retention limit", () => {
    const retained = retainPlotViewerData(snapshot(2007));
    expect(Object.keys(retained.scan_parameters.x)).toHaveLength(2007);
    expect(
      Object.keys(retained.device_data[0].readouts.result_channels.a),
    ).toHaveLength(2007);
    expect(Object.keys(retained.device_data[0].readouts.shot_channels.h)).toEqual([
      "2006",
    ]);
    expect(Object.keys(retained.device_data[0].readouts.vector_channels.v)).toEqual([
      "2006",
    ]);
  });

  it("uses maximum numeric indices for sparse, out-of-order points and duplicate counts", () => {
    const first = applyPlotViewerUpdate(EMPTY_PLOT_VIEWER_DATA, {
      type: "point",
      value: point(100, 1),
    });
    freezeDeep(first);
    const duplicate = applyPlotViewerUpdate(first, {
      type: "point",
      value: point(100, 9),
    });
    const older = applyPlotViewerUpdate(duplicate, {
      type: "point",
      value: point(9, 4),
    });
    expect(older.total_data_points).toBe(101);
    expect(older.scan_parameters.x).toEqual({ 9: 4, 100: 9 });
    expect(first.scan_parameters.x).toEqual({ 100: 1 });
    expect(first.device_data[0].readouts.result_channels.a).toEqual({ 100: 1 });
    expect(older.device_data[0].readouts.shot_channels.h).toEqual({ 100: [9] });
    expect(older.device_data[0].readouts.vector_channels.v).toEqual({ 100: [9, 10] });
    expect("hardware_instructions" in older.device_data[0]).toBe(false);
  });

  it("keeps scalar and scan indices aligned when a late update falls outside realtime retention", () => {
    const retained = retainPlotViewerData(snapshot(2001, true));
    const next = applyPlotViewerUpdate(retained, {
      type: "point",
      value: point(0, -1),
    });
    expect(Object.keys(next.scan_parameters.x)).toHaveLength(2000);
    expect(next.scan_parameters.x[0]).toBeUndefined();
    expect(next.device_data[0].readouts.result_channels.a[0]).toBeUndefined();
    expect(next.total_data_points).toBe(2001);
  });

  it("rejects invalid indices without modifying previous data", () => {
    const original = snapshot(2);
    freezeDeep(original);
    expect(() =>
      applyPlotViewerUpdate(original, { type: "point", value: point(-1) }),
    ).toThrow("index");
    expect(original.total_data_points).toBe(2);
  });
});

describe("viewer buffered snapshot replay", () => {
  it("replays point/parameter/metadata/fit edits over a snapshot without mutating held data", () => {
    const original = snapshot(2);
    original.device_data[0].fits.a = fit;
    freezeDeep(original);
    let buffer = createPlotViewerBuffer(false);
    buffer = bufferPlotViewerUpdate(buffer, { type: "point", value: point(1, 40) });
    buffer = bufferPlotViewerUpdate(buffer, { type: "point", value: point(2, 50) });
    buffer = bufferPlotViewerUpdate(buffer, {
      type: "parameters",
      value: { frequency: { value: 10, timestamp: "now" } },
    });
    buffer = bufferPlotViewerUpdate(buffer, {
      type: "metadata",
      value: [
        {
          device_id: "d",
          readout_metadata: {
            result_channels: [
              { name: "new", index: 0, type: "readout", channel_names: ["a"] },
            ],
            vector_channels: [],
            shot_channels: [],
          },
        },
      ],
    });
    buffer = bufferPlotViewerUpdate(buffer, {
      type: "fit",
      value: { device_id: "d", deleted: true, result_channel: "a" },
    });
    const replayed = replayPlotViewerBuffer(original, buffer);
    expect(replayed.scan_parameters.x).toEqual({ 0: 0, 1: 40, 2: 50 });
    expect(replayed.device_data[0].readouts.result_channels.a).toEqual({
      0: 0,
      1: 40,
      2: 50,
    });
    expect(replayed.device_data[0].readouts.result_channels.b).toEqual({ 0: 0, 1: 1 });
    expect(replayed.device_data[0].readouts.shot_channels.h).toEqual({ 2: [50] });
    expect(replayed.device_data[0].fits.a).toBeUndefined();
    expect(replayed.device_data[0].plot_windows.result_channels[0].name).toBe("new");
    expect(replayed.parameters.frequency.value).toBe(10);
    expect(replayed.total_data_points).toBe(3);
    expect(original.device_data[0].fits.a).toEqual(fit);
    expect(original.scan_parameters.x).toEqual({ 0: 0, 1: 1 });
  });

  it("preserves untouched snapshot metadata and uses last fit edit per channel", () => {
    const original = snapshot(2);
    original.device_data[0].plot_windows.result_channels = [
      { name: "existing", index: 0, type: "readout", channel_names: ["a"] },
    ];
    let buffer = createPlotViewerBuffer();
    buffer = bufferPlotViewerUpdate(buffer, { type: "point", value: point(1, 88) });
    buffer = bufferPlotViewerUpdate(buffer, {
      type: "fit",
      value: { device_id: "d", deleted: true, result_channel: "a" },
    });
    buffer = bufferPlotViewerUpdate(buffer, {
      type: "fit",
      value: { device_id: "d", fit_data: fit },
    });
    const replayed = replayPlotViewerBuffer(original, buffer);
    expect(replayed.device_data[0].plot_windows).toEqual(
      original.device_data[0].plot_windows,
    );
    expect(replayed.device_data[0].fits.a).toEqual(fit);
    expect(replayed.total_data_points).toBe(2);
  });

  it("trims replay using realtime snapshot metadata discovered after the request began", () => {
    let buffer = createPlotViewerBuffer();
    buffer = bufferPlotViewerUpdate(buffer, { type: "point", value: point(2005) });
    const replayed = replayPlotViewerBuffer(snapshot(2005, true), buffer);
    expect(Object.keys(replayed.scan_parameters.x)).toHaveLength(2000);
    expect(Object.keys(replayed.scan_parameters.x)[0]).toBe("6");
    expect(replayed.total_data_points).toBe(2006);
  });

  it("rejects malformed snapshots before replacing good data", () => {
    expect(() => validatePlotViewerSnapshot(null)).toThrow("snapshot");
    expect(() => validatePlotViewerSnapshot({ device_data: [] })).toThrow("snapshot");
    expect(() =>
      validatePlotViewerSnapshot({ ...EMPTY_PLOT_VIEWER_DATA, total_data_points: -1 }),
    ).toThrow("snapshot");
  });
});

it("preserves finite ordinary scans without realtime metadata, and explicit finite time-only snapshots", () => {
  const ordinary = snapshot(2005);
  delete ordinary.realtime_scan;
  expect(Object.keys(retainPlotViewerData(ordinary).scan_parameters.x)).toHaveLength(
    2005,
  );
  const finiteTimeOnly = snapshot(2005, false);
  delete finiteTimeOnly.scan_parameters.x;
  expect(
    Object.keys(retainPlotViewerData(finiteTimeOnly).scan_parameters.timestamp),
  ).toHaveLength(2005);
});

describe("requested realtime retention limits", () => {
  it("retains the requested size in snapshots and immutable live updates", () => {
    const original = snapshot(4500, true);
    freezeDeep(original);
    const retained = validatePlotViewerSnapshot(original, 4000);
    expect(Object.keys(retained.scan_parameters.x)).toHaveLength(4000);
    expect(Object.keys(retained.scan_parameters.x)[0]).toBe("500");
    const next = applyPlotViewerUpdate(
      retained,
      { type: "point", value: point(4500) },
      4000,
    );
    expect(Object.keys(next.scan_parameters.x)).toHaveLength(4000);
    expect(Object.keys(next.scan_parameters.x)[0]).toBe("501");
    expect(Object.keys(next.device_data[0].readouts.result_channels.a)).toEqual(
      Object.keys(next.scan_parameters.x),
    );
    expect(Object.keys(original.scan_parameters.x)).toHaveLength(4500);
  });

  it("threads a custom limit through buffered updates and snapshot replay", () => {
    const original = snapshot(8, true);
    let buffer = createPlotViewerBuffer(true);
    for (let index = 8; index < 16; index++) {
      buffer = bufferPlotViewerUpdate(
        buffer,
        { type: "point", value: point(index) },
        6,
      );
    }
    expect(Object.keys(buffer.data.scan_parameters.x)).toEqual([
      "10",
      "11",
      "12",
      "13",
      "14",
      "15",
    ]);
    const replayed = replayPlotViewerBuffer(original, buffer, 6);
    expect(Object.keys(replayed.scan_parameters.x)).toEqual([
      "10",
      "11",
      "12",
      "13",
      "14",
      "15",
    ]);
    expect(replayed.total_data_points).toBe(16);
    expect(Object.keys(replayed.device_data[0].readouts.shot_channels.h)).toEqual([
      "15",
    ]);
  });

  it("keeps finite scans unaffected even when the requested live limit is small", () => {
    const finite = retainPlotViewerData(snapshot(4500, false), 2);
    expect(Object.keys(finite.scan_parameters.x)).toHaveLength(4500);
    expect(Object.keys(finite.device_data[0].readouts.result_channels.a)).toHaveLength(
      4500,
    );
  });

  it("normalizes invalid requests to the default and caps safe positive integers", () => {
    for (const invalid of [0, -1, 2.5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) {
      expect(normalizePlotViewerLimit(invalid)).toBe(LIVE_POINT_LIMIT);
      expect(
        Object.keys(
          retainPlotViewerData(snapshot(2001, true), invalid).scan_parameters.x,
        ),
      ).toHaveLength(2000);
    }
    expect(normalizePlotViewerLimit()).toBe(2000);
    expect(normalizePlotViewerLimit(1)).toBe(1);
    expect(normalizePlotViewerLimit(4000)).toBe(4000);
    expect(normalizePlotViewerLimit(100001)).toBe(MAX_LIVE_POINT_LIMIT);
    expect(normalizePlotViewerLimit(Number.MAX_SAFE_INTEGER)).toBe(
      MAX_LIVE_POINT_LIMIT,
    );
  });
});
