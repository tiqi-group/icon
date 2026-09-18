import {
  makeScannedParamKey,
  extractScannedParamId,
  getScanIndex,
  isScannableParameterType,
  generateScanValues,
  generateScatterOrder,
  scanValueCount,
} from "../../src/utils/scanUtils";
import { ScanParameterGenerationSpec } from "../../src/types/ScanParameterGenerationSpec";

describe("scanUtils: makeScannedParamKey", () => {
  it("returns the id unchanged for experiment parameters", () => {
    expect(makeScannedParamKey("laser_power", "MyExperiment", "GroupA")).toBe(
      "laser_power",
    );
  });

  it("builds the device access path for the Devices namespace", () => {
    expect(makeScannedParamKey("laser_power", "Devices", "Laser A")).toBe(
      'devices.device_proxies["Laser A"].laser_power',
    );
  });
});

describe("scanUtils: extractScannedParamId", () => {
  it("returns the key unchanged for experiment parameters", () => {
    expect(extractScannedParamId("laser_power", "MyExperiment", "GroupA")).toBe(
      "laser_power",
    );
  });

  it("strips the device prefix for the Devices namespace", () => {
    expect(
      extractScannedParamId(
        'devices.device_proxies["Laser A"].laser_power',
        "Devices",
        "Laser A",
      ),
    ).toBe("laser_power");
  });

  it("round-trips with makeScannedParamKey", () => {
    for (const [ns, dg] of [
      ["Devices", "Laser A"],
      ["MyExperiment", "GroupA"],
    ]) {
      const key = makeScannedParamKey("freq", ns, dg);
      expect(extractScannedParamId(key, ns, dg)).toBe("freq");
    }
  });
});

describe("scanUtils: getScanIndex", () => {
  const scanned = ["a", "b", "c"];

  it("returns the index of a scanned parameter", () => {
    expect(getScanIndex("a", scanned)).toBe(0);
    expect(getScanIndex("c", scanned)).toBe(2);
  });

  it("returns null when the parameter is not scanned", () => {
    expect(getScanIndex("x", scanned)).toBeNull();
    expect(getScanIndex("a", [])).toBeNull();
  });
});

describe("scanUtils: isScannableParameterType", () => {
  it("rejects boolean and enum parameter types", () => {
    expect(isScannableParameterType("p param_type='ParameterTypes.BOOLEAN'")).toBe(
      false,
    );
    expect(isScannableParameterType("p param_type='ParameterTypes.ENUM'")).toBe(false);
  });

  it("accepts numeric/other parameter types", () => {
    expect(isScannableParameterType("p param_type='ParameterTypes.FLOAT'")).toBe(true);
    expect(isScannableParameterType("plain_param_id")).toBe(true);
  });
});

const generationSpec = (
  overrides: Partial<ScanParameterGenerationSpec> = {},
): ScanParameterGenerationSpec => ({
  start: 0,
  stop: 1,
  points: 5,
  pattern: "linear",
  ...overrides,
});

describe("scanUtils: scanValueCount", () => {
  it("returns the number of points for patterns that walk the range once", () => {
    for (const pattern of ["linear", "scatter", "centred"] as const) {
      expect(scanValueCount(generationSpec({ pattern }))).toBe(5);
    }
  });

  it("doubles the count for the forward-and-reverse pattern", () => {
    expect(scanValueCount(generationSpec({ pattern: "forwardReverse" }))).toBe(10);
  });

  it("matches the number of values generateScanValues actually produces", () => {
    for (const pattern of ["linear", "scatter", "centred", "forwardReverse"] as const) {
      const spec = generationSpec({ pattern });
      expect(
        generateScanValues(spec.start, spec.stop, spec.points, spec.pattern),
      ).toHaveLength(scanValueCount(spec));
    }
  });
});

describe("scanUtils: generateScatterOrder", () => {
  it("returns a permutation of [0, points)", () => {
    const order = generateScatterOrder(20);
    expect(order).toHaveLength(20);
    expect([...order].sort((a, b) => a - b)).toEqual(
      Array.from({ length: 20 }, (_, i) => i),
    );
  });
});

describe("scanUtils: generateScanValues scatter pattern", () => {
  it("visits the linearly spaced values in the order given by scatterOrder", () => {
    const order = [2, 0, 3, 1];
    expect(generateScanValues(0, 3, 4, "scatter", order)).toEqual([2, 0, 3, 1]);
  });

  it("keeps two parameters linearly paired when scattered with a shared order", () => {
    // Sharing the same scatterOrder across parameters is what a correlated scan must
    // do: each parameter is visited in the same shuffled sequence of underlying
    // linear indices, so the i-th scan step always pairs the i-th linear point of
    // every parameter, just in a scattered (non-monotonic) order.
    const order = generateScatterOrder(6);
    const a = generateScanValues(0, 5, 6, "scatter", order);
    const b = generateScanValues(10, 20, 6, "scatter", order);

    const aLinear = generateScanValues(0, 5, 6, "linear");
    const bLinear = generateScanValues(10, 20, 6, "linear");

    for (let i = 0; i < order.length; i++) {
      expect(a[i]).toBeCloseTo(aLinear[order[i]]);
      expect(b[i]).toBeCloseTo(bLinear[order[i]]);
    }
  });
});
