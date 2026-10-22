import { useEffect, useRef, useState } from "react";
import { runMethod, socket } from "../../../src/socket";
import { usePlotViewerData } from "../../../src/features/plot-viewer/usePlotViewerData";
import { EMPTY_PLOT_VIEWER_DATA } from "../../../src/features/plot-viewer/plotViewerData";
import type { PlotViewerData } from "../../../src/features/plot-viewer/plotViewerData";

jest.mock("react", () => ({
  useEffect: jest.fn(),
  useRef: jest.fn(),
  useState: jest.fn(),
}));
jest.mock("../../../src/socket", () => ({
  socket: { connected: true, on: jest.fn(), off: jest.fn() },
  runMethod: jest.fn(),
}));

// A small state/effect harness checks socket lifetimes without a browser or DOM.
const mockStates: unknown[] = [];
const mockRefs: { current: unknown }[] = [];
let stateCursor = 0;
let refCursor = 0;
const mockListeners = new Map<string, (...args: unknown[]) => void>();
const mockAcks: ((ack: unknown) => void)[] = [];
let cleanup: (() => void) | undefined;
const emit = (event: string, ...args: unknown[]) => mockListeners.get(event)?.(...args);
const ack = (data: PlotViewerData) => ({ type: "str", value: JSON.stringify(data) });
const data = (count: number): PlotViewerData => ({
  ...EMPTY_PLOT_VIEWER_DATA,
  total_data_points: count,
  scan_parameters: { x: { 0: 1 } },
});
const mount = (jobId = "1", limit?: number) => {
  stateCursor = 0;
  refCursor = 0;
  usePlotViewerData(jobId, limit);
  const effectCalls = (useEffect as jest.Mock).mock.calls;
  cleanup = effectCalls[effectCalls.length - 1][0]();
};
const rerender = (jobId: string, limit?: number) => {
  cleanup?.();
  mount(jobId, limit);
};

beforeEach(() => {
  jest.useFakeTimers();
  jest.clearAllMocks();
  mockStates.length = 0;
  mockRefs.length = 0;
  stateCursor = 0;
  refCursor = 0;
  mockListeners.clear();
  mockAcks.length = 0;
  socket.connected = true;
  cleanup = undefined;
  (useState as jest.Mock).mockImplementation((initial: unknown) => {
    const index = stateCursor++;
    if (index >= mockStates.length) mockStates.push(initial);
    return [
      mockStates[index],
      (next: unknown) => {
        mockStates[index] = next;
      },
    ];
  });
  (useRef as jest.Mock).mockImplementation((initial: unknown) => {
    const index = refCursor++;
    mockRefs[index] ??= { current: initial };
    return mockRefs[index];
  });
  (socket.on as jest.Mock).mockImplementation(
    (name: string, handler: (...args: unknown[]) => void) => {
      mockListeners.set(name, handler);
    },
  );
  (socket.off as jest.Mock).mockImplementation((name: string) =>
    mockListeners.delete(name),
  );
  (runMethod as jest.Mock).mockImplementation(
    (
      _path: string,
      _args: unknown[],
      _kwargs: unknown,
      callback: (value: unknown) => void,
    ) => {
      mockAcks.push(callback);
    },
  );
});
afterEach(() => {
  cleanup?.();
  jest.useRealTimers();
});

it("requests the bounded snapshot and replays updates arriving during it", () => {
  mount();
  expect(runMethod).toHaveBeenCalledWith(
    "data.get_experiment_data_by_job_id",
    [],
    {
      job_id: 1,
      max_transfer_bytes: 4_000_000,
      include_hardware_instructions: false,
      include_all_shots: false,
    },
    expect.any(Function),
  );
  expect([...mockListeners.keys()]).toEqual(
    expect.arrayContaining([
      "experiment_1",
      "experiment_1_metadata",
      "experiment_params_1",
      "experiment_fit_1",
    ]),
  );
  emit("experiment_1", {
    index: 1,
    scan_params: { x: 7 },
    timestamp: "now",
    device_data: [],
  });
  mockAcks[0](ack(data(1)));
  expect((mockStates[0] as PlotViewerData).scan_parameters.x).toEqual({ 0: 1, 1: 7 });
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(2);
  expect(mockStates[2]).toBe(false);
  expect(mockStates[4]).toBe(false);
});

it("refetches on reconnect, ignores an old acknowledgement, and keeps good data while offline", () => {
  mount();
  mockAcks[0](ack(data(5)));
  const good = mockStates[0];
  emit("disconnect");
  expect(mockStates[0]).toBe(good);
  expect(mockStates[3]).toBe(false);
  emit("connect");
  expect(mockAcks).toHaveLength(2);
  expect(mockStates[4]).toBe(true);
  mockAcks[0](ack(data(999)));
  expect(mockStates[0]).toBe(good);
  mockAcks[1](ack(data(6)));
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(6);
  expect(mockStates[3]).toBe(true);
  expect(mockStates[4]).toBe(false);
});

it("retains good data on malformed JSON and ignores callbacks after unmount", () => {
  mount();
  mockAcks[0](ack(data(5)));
  const good = mockStates[0];
  emit("connect");
  mockAcks[1]({ type: "str", value: "{" });
  expect(mockStates[0]).toBe(good);
  expect(mockStates[1]).toBeInstanceOf(Error);
  emit("connect");
  cleanup?.();
  expect(mockListeners.size).toBe(0);
  mockAcks[2](ack(data(100)));
  expect(mockStates[0]).toBe(good);
});

it("ends a stalled refresh, keeps live updates, and ignores the late snapshot", () => {
  mount();
  mockAcks[0](ack(data(1)));
  emit("connect");
  emit("experiment_1", {
    index: 5,
    scan_params: { x: 8 },
    timestamp: "now",
    device_data: [],
  });
  const live = mockStates[0];
  jest.advanceTimersByTime(20_000);
  expect(mockStates[1]).toBeInstanceOf(Error);
  expect(mockStates[4]).toBe(false);
  mockAcks[1](ack(data(100)));
  expect(mockStates[0]).toBe(live);
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(6);
});

it("bounds more than 2000 timestamp-only live events after an initial failure, then recovers snapshot metadata", () => {
  mount();
  mockAcks[0]({ type: "str", value: "{" });
  for (let index = 0; index < 2005; index++) {
    emit("experiment_1", {
      index,
      scan_params: {},
      timestamp: String(index),
      device_data: [
        {
          device_id: "d",
          hardware_instructions: "",
          readouts: {
            result_channels: { a: index },
            shot_channels: {},
            vector_channels: {},
          },
        },
      ],
    });
  }
  const retained = mockStates[0] as PlotViewerData;
  expect(retained.realtime_scan).toBeUndefined();
  expect(Object.keys(retained.scan_parameters.timestamp)).toHaveLength(2000);
  expect(Object.keys(retained.scan_parameters.timestamp)[0]).toBe("5");
  expect(Object.keys(retained.device_data[0].readouts.result_channels.a)).toEqual(
    Object.keys(retained.scan_parameters.timestamp),
  );
  expect(retained.total_data_points).toBe(2005);
  expect(mockAcks).toHaveLength(1);
  jest.advanceTimersByTime(5000);
  expect(mockAcks).toHaveLength(2);
  const windows = {
    result_channels: [
      { name: "recovered", index: 0, type: "readout" as const, channel_names: ["a"] },
    ],
    shot_channels: [],
    vector_channels: [],
  };
  const recovered: PlotViewerData = {
    ...retained,
    realtime_scan: true,
    device_data: [{ ...retained.device_data[0], plot_windows: windows }],
  };
  mockAcks[1](ack(recovered));
  expect((mockStates[0] as PlotViewerData).device_data[0].plot_windows).toEqual(
    windows,
  );
  expect(mockStates[1]).toBeNull();
  expect(mockStates[2]).toBe(false);
}, 15000);

it("coalesces metadata-triggered recovery and throttles repeated failures", () => {
  mount();
  mockAcks[0]({ type: "str", value: "{" });
  const metadata = [
    {
      device_id: "d",
      readout_metadata: { result_channels: [], shot_channels: [], vector_channels: [] },
    },
  ];
  for (let n = 0; n < 5; n++) emit("experiment_1_metadata", metadata);
  jest.advanceTimersByTime(4999);
  expect(mockAcks).toHaveLength(1);
  jest.advanceTimersByTime(1);
  expect(mockAcks).toHaveLength(2);
  mockAcks[1]({ type: "str", value: "{" });
  emit("experiment_1_metadata", metadata);
  jest.advanceTimersByTime(4999);
  expect(mockAcks).toHaveLength(2);
  jest.advanceTimersByTime(1);
  expect(mockAcks).toHaveLength(3);
  mockAcks[2](ack(data(1)));
  emit("experiment_1_metadata", metadata);
  jest.advanceTimersByTime(10000);
  expect(mockAcks).toHaveLength(3);
});

it("cancels a scheduled recovery when disconnected or unmounted", () => {
  mount();
  mockAcks[0]({ type: "str", value: "{" });
  emit("experiment_1_metadata", []);
  emit("disconnect");
  jest.advanceTimersByTime(5000);
  expect(mockAcks).toHaveLength(1);
  emit("connect");
  mockAcks[1]({ type: "str", value: "{" });
  emit("experiment_1_metadata", []);
  cleanup?.();
  jest.advanceTimersByTime(5000);
  expect(mockAcks).toHaveLength(2);
});

const realtimeData = (count: number): PlotViewerData => {
  const values = Object.fromEntries(
    Array.from({ length: count }, (_, index) => [index, index]),
  );
  return {
    ...EMPTY_PLOT_VIEWER_DATA,
    realtime_scan: true,
    total_data_points: count,
    scan_parameters: { timestamp: { ...values } },
    device_data: [
      {
        device_id: "d",
        fits: {},
        plot_windows: { result_channels: [], vector_channels: [], shot_channels: [] },
        readouts: {
          result_channels: { a: { ...values } },
          shot_channels: {},
          vector_channels: {},
        },
      },
    ],
  };
};

it("reloads a larger retention limit while preserving current data, then replays live updates", () => {
  mount("1", 3);
  mockAcks[0](ack(realtimeData(8)));
  const held = mockStates[0] as PlotViewerData;
  Object.freeze(held.scan_parameters.timestamp);
  Object.freeze(held.device_data[0].readouts.result_channels.a);
  expect(Object.keys(held.scan_parameters.timestamp)).toEqual(["5", "6", "7"]);
  rerender("1", 6);
  expect(mockAcks).toHaveLength(2);
  expect((mockStates[0] as PlotViewerData).scan_parameters).toEqual(
    held.scan_parameters,
  );
  expect(mockStates[2]).toBe(false);
  expect(mockStates[4]).toBe(true);
  // A superseded request cannot clobber current data after the effect changed.
  mockAcks[0](ack(realtimeData(100)));
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(8);
  emit("experiment_1", {
    index: 8,
    scan_params: {},
    timestamp: "8",
    device_data: [
      {
        device_id: "d",
        readouts: {
          result_channels: { a: 80 },
          shot_channels: {},
          vector_channels: {},
        },
      },
    ],
  });
  mockAcks[1](ack(realtimeData(8)));
  const expanded = mockStates[0] as PlotViewerData;
  expect(Object.keys(expanded.scan_parameters.timestamp)).toEqual([
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
  ]);
  expect(expanded.device_data[0].readouts.result_channels.a[8]).toBe(80);
  expect(expanded.total_data_points).toBe(9);
  expect(mockStates[4]).toBe(false);
  expect(Object.keys(held.scan_parameters.timestamp)).toEqual(["5", "6", "7"]);
  expect(held.device_data[0].readouts.result_channels.a[7]).toBe(7);
  expect((runMethod as jest.Mock).mock.calls[1][2].max_transfer_bytes).toBe(4_000_000);
});

it("uses the new retention limit for shrinking, reconnect snapshots, and buffered updates", () => {
  mount("1", 6);
  mockAcks[0](ack(realtimeData(8)));
  rerender("1", 2);
  expect(
    Object.keys((mockStates[0] as PlotViewerData).scan_parameters.timestamp),
  ).toEqual(["6", "7"]);
  emit("disconnect");
  emit("connect");
  expect(mockAcks).toHaveLength(3);
  mockAcks[1](ack(realtimeData(100)));
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(8);
  emit("experiment_1", { index: 8, scan_params: {}, timestamp: "8", device_data: [] });
  mockAcks[2](ack(realtimeData(8)));
  expect(
    Object.keys((mockStates[0] as PlotViewerData).scan_parameters.timestamp),
  ).toEqual(["7", "8"]);
});

it("keeps data when the larger-history fetch fails, but resets when the job changes", () => {
  mount("1", 3);
  mockAcks[0](ack(realtimeData(8)));
  rerender("1", 6);
  const good = mockStates[0];
  mockAcks[1]({ type: "str", value: "{" });
  expect(mockStates[0]).toBe(good);
  expect(mockStates[1]).toBeInstanceOf(Error);
  rerender("2", 6);
  expect((mockStates[0] as PlotViewerData).total_data_points).toBe(0);
  expect(mockStates[2]).toBe(true);
  expect(mockListeners.has("experiment_1")).toBe(false);
  expect(mockListeners.has("experiment_2")).toBe(true);
});
