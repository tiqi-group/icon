import {
  brushZoomRanges,
  scaleZoomRanges,
} from "../../../src/features/plot-viewer/viewerZoom";

describe("scaleZoomRanges", () => {
  const ranges = [
    { id: "viewer-x", start: 20, end: 60 },
    { id: "viewer-y", start: 10, end: 90 },
    { id: "other", start: 0, end: 100 },
  ];

  it("scales independent axis ranges around their own centres", () => {
    expect(scaleZoomRanges(ranges, "both", 0.5)).toEqual([
      { dataZoomId: "viewer-x", start: 30, end: 50 },
      { dataZoomId: "viewer-y", start: 30, end: 70 },
    ]);
    expect(ranges[0]).toEqual({ id: "viewer-x", start: 20, end: 60 });
  });

  it("emits only the chosen axis so the other axis stays untouched", () => {
    expect(scaleZoomRanges(ranges, "x", 0.5)).toEqual([
      { dataZoomId: "viewer-x", start: 30, end: 50 },
    ]);
    expect(scaleZoomRanges(ranges, "y", 0.5)).toEqual([
      { dataZoomId: "viewer-y", start: 30, end: 70 },
    ]);
    expect(scaleZoomRanges([{ id: "other", start: 0, end: 100 }], "both", 1)).toEqual(
      [],
    );
  });

  it("shifts expanded ranges inside bounds while preserving their width", () => {
    expect(
      scaleZoomRanges(
        [
          { id: "viewer-x", start: 0, end: 10 },
          { id: "viewer-y", start: 90, end: 100 },
        ],
        "both",
        2,
      ),
    ).toEqual([
      { dataZoomId: "viewer-x", start: 0, end: 20 },
      { dataZoomId: "viewer-y", start: 80, end: 100 },
    ]);
    expect(scaleZoomRanges(ranges, "both", 100)).toEqual([
      { dataZoomId: "viewer-x", start: 0, end: 100 },
      { dataZoomId: "viewer-y", start: 0, end: 100 },
    ]);
  });

  it("enforces minimum width, including a collapsed range at either boundary", () => {
    const scaled = scaleZoomRanges(
      [
        { id: "viewer-x", start: 0, end: 0 },
        { id: "viewer-y", start: 100, end: 100 },
      ],
      "both",
      0.000001,
    );
    for (const range of scaled) {
      expect(range.start).toBeGreaterThanOrEqual(0);
      expect(range.end).toBeLessThanOrEqual(100);
      expect(range.end - range.start).toBeCloseTo(0.1, 10);
    }
  });

  it("normalizes reversed and out-of-bounds percentages", () => {
    expect(
      scaleZoomRanges(
        [
          { id: "viewer-x", start: 120, end: -20 },
          { id: "viewer-y", start: 60, end: 20 },
        ],
        "both",
        0.5,
      ),
    ).toEqual([
      { dataZoomId: "viewer-x", start: 25, end: 75 },
      { dataZoomId: "viewer-y", start: 30, end: 50 },
    ]);
  });

  it.each([0, -1, NaN, Infinity, -Infinity])("rejects invalid factor %s", (factor) => {
    expect(scaleZoomRanges(ranges, "both", factor)).toEqual([]);
  });

  it("rejects nonfinite input ranges without dropping valid independent axes", () => {
    expect(
      scaleZoomRanges(
        [
          { id: "viewer-x", start: NaN, end: 100 },
          { id: "viewer-y", start: 10, end: 30 },
          { id: "viewer-x", start: 0, end: Infinity },
        ],
        "both",
        1,
      ),
    ).toEqual([{ dataZoomId: "viewer-y", start: 10, end: 30 }]);
  });
});

describe("brushZoomRanges", () => {
  it("keeps asymmetric rectangle coordinates independent and sorts each range", () => {
    expect(
      brushZoomRanges({
        brushType: "rect",
        coordRange: [
          [8, 2],
          [-50, -20],
        ],
      }),
    ).toEqual([
      { dataZoomId: "viewer-x", startValue: 2, endValue: 8 },
      { dataZoomId: "viewer-y", startValue: -50, endValue: -20 },
    ]);
  });

  it("changes only the axis selected by a line brush", () => {
    expect(brushZoomRanges({ brushType: "lineX", coordRange: [9, -3] })).toEqual([
      { dataZoomId: "viewer-x", startValue: -3, endValue: 9 },
    ]);
    expect(brushZoomRanges({ brushType: "lineY", coordRange: [100, 400] })).toEqual([
      { dataZoomId: "viewer-y", startValue: 100, endValue: 400 },
    ]);
  });

  it.each(
    [
      undefined,
      null,
      [],
      [1],
      [1, 2, 3],
      [1, 1],
      [NaN, 1],
      [0, Infinity],
      ["1", 2],
      [
        [1, 2],
        [3, 4],
      ],
      { start: 1, end: 2 },
    ].map((coordRange) => ({ coordRange })),
  )("rejects malformed line ranges %p", ({ coordRange }) => {
    expect(brushZoomRanges({ brushType: "lineX", coordRange })).toEqual([]);
    expect(brushZoomRanges({ brushType: "lineY", coordRange })).toEqual([]);
  });

  it.each(
    [
      [
        [1, 1],
        [2, 3],
      ],
      [
        [1, 2],
        [3, 3],
      ],
      [
        [1, 2],
        [NaN, 4],
      ],
      [[1, 2]],
      [
        [1, 2],
        [3, 4],
        [5, 6],
      ],
      [1, 2],
    ].map((coordRange) => ({ coordRange })),
  )(
    "rejects the entire rectangle when either axis is invalid: %p",
    ({ coordRange }) => {
      expect(brushZoomRanges({ brushType: "rect", coordRange })).toEqual([]);
    },
  );

  it("ignores missing and unsupported brush types", () => {
    expect(brushZoomRanges()).toEqual([]);
    expect(brushZoomRanges({ coordRange: [1, 2] })).toEqual([]);
    expect(
      brushZoomRanges({
        brushType: "polygon",
        coordRange: [
          [1, 2],
          [3, 4],
        ],
      }),
    ).toEqual([]);
  });
});
