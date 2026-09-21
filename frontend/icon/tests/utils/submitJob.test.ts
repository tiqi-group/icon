jest.mock("../../src/socket", () => ({
  runMethod: jest.fn(),
  forwardedPrefix: "",
  hostname: "localhost",
  port: 8004,
}));

import { generateScanValues } from "../../src/utils/submitJob";

describe("submitJob: generateScanValues", () => {
  it("generates evenly spaced values for the linear pattern", () => {
    expect(generateScanValues(1, 10, 10, "linear")).toEqual([
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
    ]);
  });
});
