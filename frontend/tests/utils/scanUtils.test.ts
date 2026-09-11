import {
  makeScannedParamKey,
  extractScannedParamId,
  getScanIndex,
  isScannableParameterType,
  refreshSpanCenterParameters,
  getScanParameterBounds,
  getScanParameterDisplayName,
  clampToBounds,
} from "../../src/utils/scanUtils";
import { ScanParameterInfo } from "../../src/types/ScanParameterInfo";
import {
  ParameterMetadata,
  ParameterValueType,
} from "../../src/types/ExperimentMetadata";

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

describe("scanUtils: refreshSpanCenterParameters", () => {
  const param = (
    id: string,
    inputMode: "startStop" | "spanCenter",
    start: number,
    stop: number,
  ): ScanParameterInfo => ({
    id,
    namespace: "E",
    deviceNameOrDisplayGroup: "grp",
    generation: { start, stop, points: 2, pattern: "linear", inputMode },
  });

  const storeOf = (values: Record<string, ParameterValueType>) => ({
    get: (key: string) => values[key],
  });

  it("re-centres a Span-mode parameter on its live value, keeping the span", () => {
    const parameters = [param("p1", "spanCenter", 10, 20)]; // span 10, old center 15
    const refreshed = refreshSpanCenterParameters(parameters, storeOf({ p1: 42 }));

    expect(refreshed[0].generation.start).toBe(37);
    expect(refreshed[0].generation.stop).toBe(47);
  });

  it("leaves Start/Stop-mode parameters untouched", () => {
    const parameters = [param("p1", "startStop", 10, 20)];
    const refreshed = refreshSpanCenterParameters(parameters, storeOf({ p1: 42 }));

    expect(refreshed[0]).toBe(parameters[0]);
  });

  it("leaves a Span-mode parameter untouched when its live value isn't numeric", () => {
    const parameters = [param("p1", "spanCenter", 10, 20)];
    expect(refreshSpanCenterParameters(parameters, storeOf({}))).toEqual(parameters);
    expect(refreshSpanCenterParameters(parameters, null)).toEqual(parameters);
  });
});

describe("scanUtils: getScanParameterBounds / getScanParameterDisplayName", () => {
  const metadata: ParameterMetadata = {
    display_name: "pulse time",
    unit: "us",
    default_value: 30,
    min_value: 10,
    max_value: null,
  };
  // Same metadata under device and realtime keys, to check those are never looked up.
  const groups = {
    "E (grp)": { p1: metadata },
    "Devices (grp)": { p1: metadata },
    "Real Time (grp)": { p1: metadata },
  };
  const param = (namespace: string, id = "p1"): ScanParameterInfo => ({
    id,
    namespace,
    deviceNameOrDisplayGroup: "grp",
    generation: { start: 0, stop: 1, points: 2, pattern: "linear" },
  });

  it("reads bounds and display name from the parameter's display group", () => {
    expect(getScanParameterBounds(param("E"), groups)).toEqual({ min: 10, max: null });
    expect(getScanParameterDisplayName(param("E"), groups)).toBe("pulse time");
  });

  it("has no bounds and uses the id for unknown, device and realtime parameters", () => {
    for (const p of [param("E", "unknown"), param("Devices"), param("Real Time")]) {
      expect(getScanParameterBounds(p, groups)).toEqual({ min: null, max: null });
      expect(getScanParameterDisplayName(p, groups)).toBe(p.id);
    }
  });
});

describe("scanUtils: clampToBounds", () => {
  it("clamps out-of-range values to the nearest bound", () => {
    expect(clampToBounds(8, { min: 10, max: 20 })).toBe(10);
    expect(clampToBounds(25, { min: 10, max: 20 })).toBe(20);
    expect(clampToBounds(15, { min: 10, max: 20 })).toBe(15);
  });

  it("does not clamp against a missing bound", () => {
    expect(clampToBounds(-1e9, { min: null, max: 20 })).toBe(-1e9);
    expect(clampToBounds(1e9, { min: 10, max: null })).toBe(1e9);
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
