import { formatNum, xDecimalsFromValues } from "../../src/utils/plotAxisFormatting";

describe("xDecimalsFromValues", () => {
  it("keeps one decimal when points are 1 apart but not integers", () => {
    expect(xDecimalsFromValues([2.5, 3.5, 4.5, 5.5, 6.5])).toBe(1);
    expect(formatNum(2.5, 1)).toBe("2.5");
    expect(formatNum(4.5, 1)).toBe("4.5");
    expect(formatNum(6.5, 1)).toBe("6.5");
  });

  it("uses 0 decimals for integer scans with step 1", () => {
    expect(xDecimalsFromValues([0, 1, 2, 3])).toBe(0);
    expect(formatNum(2, 0)).toBe("2");
  });

  it("uses 1 decimal for a 0 to 1 scan with 11 points", () => {
    const values = Array.from({ length: 11 }, (_, i) => i / 10);
    expect(xDecimalsFromValues(values)).toBe(1);
  });

  it("uses the value itself for a single non-integer point", () => {
    expect(xDecimalsFromValues([2.5])).toBe(1);
  });

  it("collapses IEEE-754 artifacts to 1 decimal", () => {
    expect(xDecimalsFromValues([0, 0.30000000000000004, 1])).toBe(1);
    expect(formatNum(0.30000000000000004, 1)).toBe("0.3");
  });
});
