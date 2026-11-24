import { build2DHeatmapData } from "../../src/utils/build2DHeatmapData";

const ts = (s: number) => `2026-11-24T10:00:${String(s).padStart(2, "0")}Z`;

describe("build2DHeatmapData", () => {
  it("labels each sweep with the timestamp of its first point (realtime y)", () => {
    // 3 x values, two complete sweeps; a pause between the sweeps
    const timestamps = [ts(0), ts(1), ts(2), ts(30), ts(31), ts(32)];
    const { data, sweepLabels } = build2DHeatmapData(
      { realtime: false, scanValues: [1, 2, 3] },
      { realtime: true, scanValues: [] },
      [10, 11, 12, 13, 14, 15],
      timestamps,
    );

    expect(sweepLabels).toEqual([ts(0), ts(30)]);
    expect(data.map((p) => p.value)).toEqual([
      ["1", ts(0), 10],
      ["2", ts(0), 11],
      ["3", ts(0), 12],
      ["1", ts(30), 13],
      ["2", ts(30), 14],
      ["3", ts(30), 15],
    ]);
    expect(data.map((p) => p.timestamp)).toEqual(timestamps);
  });

  it("handles a realtime x axis and an incomplete last sweep", () => {
    const timestamps = [ts(0), ts(1), ts(5)];
    const { data, sweepLabels } = build2DHeatmapData(
      { realtime: true, scanValues: [] },
      { realtime: false, scanValues: [7, 8] },
      [1, 2, 3],
      timestamps,
    );

    expect(sweepLabels).toEqual([ts(0), ts(5)]);
    expect(data.map((p) => p.value)).toEqual([
      [ts(0), "7", 1],
      [ts(0), "8", 2],
      [ts(5), "7", 3],
    ]);
    expect(data[2].timestamp).toBe(ts(5));
  });

  it("builds the full grid when no axis is realtime", () => {
    const { data, sweepLabels } = build2DHeatmapData(
      { realtime: false, scanValues: [1, 2] },
      { realtime: false, scanValues: [3, 4] },
      [10, 11, 12, 13],
      [],
    );

    expect(sweepLabels).toEqual([]);
    expect(data.map((p) => p.value)).toEqual([
      ["1", "3", 10],
      ["1", "4", 11],
      ["2", "3", 12],
      ["2", "4", 13],
    ]);
  });
});
