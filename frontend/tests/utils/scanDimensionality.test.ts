import { isCorrelatedScan } from "../../src/utils/scanDimensionality";
import { ScanMode } from "../../src/types/enums";
import { ScanParameter } from "../../src/types/ScanParameter";

const param = (overrides: Partial<ScanParameter> = {}): ScanParameter => ({
  id: 1,
  job_id: 1,
  name: "p",
  scan_values: [],
  variable_id: "p",
  realtime: false,
  ...overrides,
});

describe("scanDimensionality: isCorrelatedScan", () => {
  it("is false when the scan mode is not correlated", () => {
    expect(isCorrelatedScan([param(), param()], ScanMode.MESH)).toBe(false);
  });

  it("is false with zero scan parameters, even in correlated mode", () => {
    expect(isCorrelatedScan([], ScanMode.CORRELATED)).toBe(false);
    expect(isCorrelatedScan(undefined, ScanMode.CORRELATED)).toBe(false);
  });

  it("is false with a single scan parameter, even in correlated mode", () => {
    expect(isCorrelatedScan([param()], ScanMode.CORRELATED)).toBe(false);
  });

  it("is true with two or more non-realtime parameters in correlated mode", () => {
    expect(isCorrelatedScan([param(), param()], ScanMode.CORRELATED)).toBe(true);
    expect(isCorrelatedScan([param(), param(), param()], ScanMode.CORRELATED)).toBe(
      true,
    );
  });

  it("is false when a realtime parameter is present", () => {
    expect(
      isCorrelatedScan([param(), param({ realtime: true })], ScanMode.CORRELATED),
    ).toBe(false);
  });

  it("is false when scanMode is undefined", () => {
    expect(isCorrelatedScan([param(), param()], undefined)).toBe(false);
  });
});
