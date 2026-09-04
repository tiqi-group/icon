import {
  makeScannedParamKey,
  extractScannedParamId,
  getScanIndex,
  isScannableParameterType,
  generateScanValues,
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
