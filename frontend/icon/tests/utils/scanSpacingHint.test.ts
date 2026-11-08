jest.mock("../../src/socket", () => ({
  runMethod: jest.fn(),
  forwardedPrefix: "",
  hostname: "localhost",
  port: 8004,
}));

import { ScanParameterInfo, scanPatterns } from "../../src/types/ScanParameterInfo";
import { scanSpacingHint } from "../../src/utils/scanSpacingHint";
import { generateScanValues } from "../../src/utils/submitJob";

const parameter: ScanParameterInfo = {
  id: "frequency",
  namespace: "experiment",
  deviceNameOrDisplayGroup: "Pulse",
  generation: { start: 10, stop: 12, points: 5, pattern: "linear" },
};
const unbounded = { min: null, max: null };

test.each(scanPatterns)(
  "%s reports grid spacing consistent with generated values",
  (pattern) => {
    const scan = { ...parameter, generation: { ...parameter.generation, pattern } };
    const values = [...new Set(generateScanValues(10, 12, 5, pattern))].sort(
      (a, b) => a - b,
    );
    expect(values[1] - values[0]).toBe(0.5);
    expect(scanSpacingHint(scan, unbounded, "MHz", undefined)).toBe(
      (pattern === "linear" ? "Step size" : "Grid spacing") + ": 0.5 MHz",
    );
  },
);

test("refreshes the live Span center before clamping endpoints", () => {
  const scan: ScanParameterInfo = {
    ...parameter,
    generation: {
      ...parameter.generation,
      start: 0,
      stop: 4,
      inputMode: "spanCenter",
    },
  };
  expect(scanSpacingHint(scan, { min: 0, max: 10 }, "MHz", 9)).toBe(
    "Step size: 0.75 MHz (limited by bounds)",
  );
  expect(scanSpacingHint(scan, { min: 0, max: 10 }, "MHz", 5)).toBe("Step size: 1 MHz");
});

test("keeps descending direction and small nonzero spacing", () => {
  expect(
    scanSpacingHint(
      {
        ...parameter,
        generation: {
          ...parameter.generation,
          start: 12,
          stop: 10,
        },
      },
      unbounded,
      "MHz",
      undefined,
    ),
  ).toBe("Step size: -0.5 MHz");
  expect(
    scanSpacingHint(
      {
        ...parameter,
        generation: {
          ...parameter.generation,
          start: 0,
          stop: 0.00000004,
        },
      },
      unbounded,
      "s",
      undefined,
    ),
  ).toBe("Step size: 1e-8 s");
});

test("distinguishes single-point and zero-span scans", () => {
  expect(
    scanSpacingHint(
      {
        ...parameter,
        generation: {
          ...parameter.generation,
          points: 1,
        },
      },
      unbounded,
      "MHz",
      undefined,
    ),
  ).toBe("Single point — no step");
  expect(
    scanSpacingHint(
      {
        ...parameter,
        generation: {
          ...parameter.generation,
          stop: 10,
        },
      },
      unbounded,
      undefined,
      undefined,
    ),
  ).toBe("Step size: 0");
});

test.each([0, -1, 1.5, NaN, Infinity])(
  "does not invent a step for invalid points %s",
  (points) => {
    expect(
      scanSpacingHint(
        {
          ...parameter,
          generation: {
            ...parameter.generation,
            points,
          },
        },
        unbounded,
        "MHz",
        undefined,
      ),
    ).toBeNull();
  },
);

test("omits spacing for real-time and unselected parameters", () => {
  expect(
    scanSpacingHint({ ...parameter, namespace: "Real Time" }, unbounded, "s", 1),
  ).toBeNull();
  expect(scanSpacingHint({ ...parameter, id: "" }, unbounded, "MHz", 1)).toBeNull();
});
