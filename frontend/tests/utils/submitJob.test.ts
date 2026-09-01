jest.mock("../../src/socket", () => ({
  runMethod: jest.fn(),
}));
jest.mock("../../src/utils/windowUtils", () => ({
  openJobWindow: jest.fn(),
}));

import { generateScanValues } from "../../src/utils/submitJob";

describe("generateScanValues", () => {
  it("avoids IEEE-754 artifacts in a linear 0 to 1 scan with 11 points", () => {
    const values = generateScanValues(0, 1, 11, "linear");
    expect(values).toContain(0.3);
    expect(values).not.toContain(0.30000000000000004);
  });
});
