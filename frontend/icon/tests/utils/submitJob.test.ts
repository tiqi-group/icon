jest.mock("../../src/socket", () => ({
  runMethod: jest.fn(),
  forwardedPrefix: "",
  hostname: "localhost",
  port: 8004,
}));

import { generateScanValues } from "../../src/utils/submitJob";
import { scanValueCount } from "../../src/utils/scanUtils";

describe("submitJob: generateScanValues", () => {
  it("generates evenly spaced values for the linear pattern", () => {
    expect(generateScanValues(1, 10, 10, "linear")).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    ]);
  });
});

describe("submitJob: generateScanValues vs scanUtils.scanValueCount", () => {
  it("produces as many values as scanValueCount predicts", () => {
    for (const pattern of ["linear", "scatter", "centred", "forwardReverse"] as const) {
      const spec = { start: 0, stop: 4, points: 5, pattern };
      expect(
        generateScanValues(spec.start, spec.stop, spec.points, spec.pattern),
      ).toHaveLength(scanValueCount(spec));
    }
  });
});
