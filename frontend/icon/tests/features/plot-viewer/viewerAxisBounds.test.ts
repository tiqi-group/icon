import {
  axisBounds,
  axisInputType,
  resolveAxisBounds,
} from "../../../src/features/plot-viewer/viewerAxisBounds";

test("numeric limits are actual values, including zero, and Auto restores the source extent", () => {
  expect(axisBounds({ type: "value", min: "dataMin", max: "dataMax" }, 0, 10)).toEqual({
    min: 0,
    max: 10,
  });
  expect(axisBounds({ type: "value", min: "dataMin" }, null, null)).toEqual({
    min: "dataMin",
    max: null,
  });
});
test("heatmap coordinates map to inclusive category indices, not value-as-index", () => {
  const axis = { type: "category", data: ["-4", "-2", "0", "2", "4"] };
  expect(axisBounds(axis, -1, 3)).toEqual({ min: 2, max: 3 });
  expect(axisBounds(axis, null, -2)).toEqual({ min: 0, max: 1 });
  expect(axisBounds(axis, 4, null)).toEqual({ min: 4, max: 4 });
  expect(() => axisBounds(axis, 8, 9)).toThrow("No axis samples");
});
test("invalid or inverted limits never replace the active range", () => {
  expect(() => axisBounds({ type: "value" }, 2, 1)).toThrow();
  expect(() => axisBounds({ type: "value" }, 1, 1)).toThrow();
  expect(() => axisBounds({ type: "value" }, Infinity, null)).toThrow();
});
test("time axes and time categories use datetime controls with timestamp bounds", () => {
  const times = [
    "2026-10-22T06:00:00Z",
    "2026-10-22T06:01:00Z",
    "2026-10-22T06:02:00Z",
  ];
  const axis = { type: "category", data: times };
  expect(axisInputType(axis)).toBe("datetime-local");
  expect(axisInputType({ type: "time" })).toBe("datetime-local");
  expect(axisBounds(axis, Date.parse(times[1]), null)).toEqual({ min: 1, max: 2 });
  expect(axisInputType({ type: "category", data: ["red", "blue"] })).toBeNull();
});

test("implicit value axes enable numeric controls while an absent axis stays disabled", () => {
  expect(axisInputType({})).toBe("number");
  expect(axisInputType({ min: 0, max: 10 })).toBe("number");
  expect(axisInputType(undefined)).toBeNull();
});

test("changing category samples invalidates old limits safely and Auto recovers", () => {
  const before = { type: "category", data: ["0", "1", "2"] };
  const after = { type: "category", data: ["10", "11", "12"] };
  expect(resolveAxisBounds(before, 0, 2)).toEqual({
    valid: true,
    bounds: { min: 0, max: 2 },
  });
  expect(resolveAxisBounds(after, 0, 2)).toEqual({
    valid: false,
    error: "No axis samples fall within these limits.",
  });
  // Apply keeps strict validation; render-time resolution returns an error instead.
  expect(() => axisBounds(after, 0, 2)).toThrow("No axis samples");
  expect(resolveAxisBounds(after, null, null)).toEqual({
    valid: true,
    bounds: { min: null, max: null },
  });
  expect(after.data).toEqual(["10", "11", "12"]);
});

test("a rolling time category can invalidate a previously valid upper bound without throwing", () => {
  const oldTime = "2026-10-22T06:00:00Z";
  const nextTime = "2026-10-22T07:00:00Z";
  const max = Date.parse("2026-10-22T06:30:00Z");
  expect(
    resolveAxisBounds({ type: "category", data: [oldTime] }, null, max).valid,
  ).toBe(true);
  expect(
    resolveAxisBounds({ type: "category", data: [nextTime] }, null, max).valid,
  ).toBe(false);
  expect(resolveAxisBounds({ type: "category", data: [] }, null, max).valid).toBe(
    false,
  );
});
