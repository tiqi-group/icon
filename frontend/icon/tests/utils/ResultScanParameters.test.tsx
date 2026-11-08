import { renderToStaticMarkup } from "react-dom/server";
import { ResultScanParameters } from "../../src/components/jobView/ResultScanParameters";
import {
  SavedScanParameter,
  resultScanKey,
  scanBounds,
  resultScanIdentity,
  resultScanSpacing,
} from "../../src/utils/resultScanParameters";
import { ParameterValueType } from "../../src/types/ExperimentMetadata";

jest.mock("../../src/components/jobView/ResultScanParameters.css", () => ({}));

const scan = (
  variable_id: string,
  scan_values: ParameterValueType[],
  extra: Partial<SavedScanParameter> = {},
): SavedScanParameter => ({
  id: 1,
  job_id: 1,
  variable_id,
  name: "",
  scan_values,
  realtime: false,
  ...extra,
});
const metadata = (name: string, unit = "") => ({
  display_name: name,
  unit,
  default_value: 0,
  min_value: null,
  max_value: null,
});

describe("saved scan parameter frame", () => {
  it("lists both axes and their ranges, but does not render fixed parameters", () => {
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{
          Group: {
            p1: metadata("Parameter 1", "MHz"),
            p2: metadata("Parameter 2", "ms"),
            fixed: metadata("Fixed"),
          },
        }}
        scanParameters={[scan("p1", [1, 2, 3, 4, 5]), scan("p2", [3, 4, 5, 6, 7])]}
      />,
    );
    expect(html).toContain('aria-label="Scan Parameters"');
    expect(html).toContain('aria-label="Scan 1"');
    expect(html).toContain('aria-label="Scan 2"');
    expect(html).toContain("Parameter 1");
    expect(html).toContain("Parameter 2");
    for (const value of [1, 3, 5, 7]) expect(html).toContain(`>${value}</dd>`);
    expect(html).toContain("Min (MHz)");
    expect(html).toContain("Max (ms)");
    expect(html).toContain("Span (MHz)");
    expect(html).toContain("Center (MHz)");
    expect(html).toContain("Step size (ms)");
    expect(html).toContain("Namespace");
    expect(html).toContain("Display Group");
    expect(html).not.toContain("Fixed");
    expect(html).not.toContain("default_value");
    expect(html).not.toContain("<input");
  });

  it("preserves every available digit in long and very small bounds", () => {
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{}}
        scanParameters={[
          scan("Precision", [1.2345678901234567, 5.678901234567891]),
          scan("Large", [85000000.12345678, 85000004.98765433]),
          scan("Small", [-1.2345678901234567e-12, 5.678901234567891e-12]),
        ]}
      />,
    );
    for (const value of [
      "1.2345678901234567",
      "5.678901234567891",
      "85000000.12345678",
      "85000004.98765433",
      "-1.2345678901234567e-12",
      "5.678901234567891e-12",
    ])
      expect(html).toContain(`>${value}</dd>`);
  });

  it("identifies device scans separately even when variable IDs match", () => {
    const a = scan("frequency", [1, 5], {
      device_id: 7,
      device: { id: 7, name: "Laser A" },
    });
    const b = scan("frequency", [3, 7], {
      device_id: 8,
      device: { id: 8, name: "Laser B" },
    });
    expect(resultScanKey(a)).toBe("Device(Laser A) frequency");
    expect(resultScanKey(b)).toBe("Device(Laser B) frequency");
    expect(resultScanKey(scan("frequency", []))).toBe("frequency");
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{ Group: { frequency: metadata("Experiment frequency", "Hz") } }}
        scanParameters={[a, b]}
      />,
    );
    expect(html).toContain(">Laser A</dd>");
    expect(html).toContain(">Laser B</dd>");
    expect(html).toContain("Device Name");
    expect(html).toContain(">Devices</dd>");
    expect(html).not.toContain("Experiment frequency");
    expect(html).not.toContain("Hz");
  });

  it("reports missing range values without inventing defaults", () => {
    const html = renderToStaticMarkup(
      <ResultScanParameters parameters={{}} scanParameters={[scan("Missing", [])]} />,
    );
    expect(html).toContain("Range unavailable");
    expect(html).toContain('aria-label="Scan 1"');
  });

  it("omits the frame for unscanned and realtime-only jobs", () => {
    expect(
      renderToStaticMarkup(
        <ResultScanParameters parameters={{}} scanParameters={[]} />,
      ),
    ).toBe("");
    expect(
      renderToStaticMarkup(
        <ResultScanParameters
          parameters={{}}
          scanParameters={[scan("Real Time", [], { realtime: true })]}
        />,
      ),
    ).toBe("");
  });
});

describe("saved scan identity", () => {
  const id = (namespace: string, group = "internal") =>
    `namespace='${namespace}' parameter_group='${group}' param_type='ParameterTypes.FREQUENCY' name='frequency'`;
  it("distinguishes matching names by namespace and metadata display group", () => {
    const global = id("experiment_library.globals.global_parameters");
    const local = id("experiments.Spectroscopy.Carrier");
    const parameters = {
      "Doppler cooling": { [global]: metadata("Frequency", "MHz") },
      "Carrier pulse": { [local]: metadata("Frequency", "MHz") },
    };
    expect(
      resultScanIdentity(
        scan(global, [1, 5]),
        parameters,
        "experiments.Spectroscopy (Carrier)",
      ),
    ).toMatchObject({
      namespaceLabel: "Global Parameters",
      group: "Doppler cooling",
      name: "Frequency",
      unit: "MHz",
    });
    expect(
      resultScanIdentity(
        scan(local, [3, 7]),
        parameters,
        "experiments.Spectroscopy (Carrier)",
      ),
    ).toMatchObject({
      namespaceLabel: "Carrier",
      namespace: "experiments.Spectroscopy.Carrier",
      group: "Carrier pulse",
      name: "Frequency",
    });
  });
  it("falls back to recorded identifiers without mixing in another parameter's metadata", () => {
    expect(
      resultScanIdentity(
        scan(id("experiments.Old.Instance", "Saved group"), [1, 5], {
          name: "Saved name",
        }),
        {},
        "experiments.New (Instance)",
      ),
    ).toMatchObject({
      namespace: "experiments.Old.Instance",
      group: "Saved group",
      groupFromIdentifier: true,
      name: "Saved name",
    });
    expect(resultScanIdentity(scan("legacy", []), {})).toMatchObject({
      namespace: "Not recorded",
      group: "Not recorded",
      name: "legacy",
    });
  });
  it("reads quoted namespaces and names", () => {
    expect(
      resultScanIdentity(
        scan(
          'namespace="experiments.O\'Brien" parameter_group="Cooling" name="frequency"',
          [],
          { name: "" },
        ),
        {},
      ),
    ).toMatchObject({
      namespace: "experiments.O'Brien",
      group: "Cooling",
      name: "frequency",
    });
  });
});

describe("saved scan span and step", () => {
  it("does not hide irregular steps when absolute values are very large", () => {
    expect(resultScanSpacing([1e16, 1e16 + 2, 1e16 + 6]).step).toBe("Variable");
  });
  it.each([
    [[1, 2, 3, 4, 5], { span: "4", step: "1", reordered: false }],
    [[7, 5, 3], { span: "4", step: "-2", reordered: false }],
    [[1, 3, 2, 5, 4], { span: "4", step: "1", reordered: true }],
    [[1, 2, 3, 2, 1], { span: "2", step: "1", reordered: true }],
    [[1, 2, 4], { span: "3", step: "Variable", reordered: false }],
    [[3], { span: "0", step: "No step", reordered: false }],
    [[3, 3], { span: "0", step: "No step", reordered: false }],
    [[], { span: "Unavailable", step: "Unavailable", reordered: false }],
  ] as [number[], ReturnType<typeof resultScanSpacing>][])(
    "handles %j",
    (values, expected) => expect(resultScanSpacing(values)).toEqual(expected),
  );

  it("tolerates float reconstruction noise without rounding displayed values", () => {
    const values = Array.from({ length: 6 }, (_, i) => 0.1 + i * 0.1);
    expect(resultScanSpacing(values).step).not.toBe("Variable");
    const min = 1.2345678901234567,
      max = 5.678901234567891;
    expect(resultScanSpacing([min, max])).toMatchObject({
      span: String(max - min),
      step: String(max - min),
    });
    expect(resultScanSpacing([85000000, 85000000.001, 85000000.003]).step).toBe(
      "Variable",
    );
  });
});

describe("saved bounds", () => {
  it.each([
    [
      [5, 3, 1],
      [1, 5],
    ],
    [
      [1, 5, 2, 4, 3],
      [1, 5],
    ],
    [
      [-5, -1, -3],
      [-5, -1],
    ],
    [
      [0.001, 0.009],
      [0.001, 0.009],
    ],
    [[3], [3, 3]],
    [
      [3, 3, 3],
      [3, 3],
    ],
    [[], null],
  ] as [number[], [number, number] | null][])("handles %j", (values, expected) =>
    expect(scanBounds(values)).toEqual(expected),
  );
  it("does not assume categorical values form a numeric interval", () => {
    expect(scanBounds([false, true])).toBeNull();
    expect(scanBounds(["A", "B"])).toBeNull();
  });
  it("handles long scans without argument spreading", () => {
    expect(scanBounds(Array.from({ length: 200000 }, (_, i) => i))).toEqual([
      0, 199999,
    ]);
  });
});

describe("saved scan edge cases", () => {
  it("keeps a saved name when current metadata has been renamed", () => {
    expect(
      resultScanIdentity(scan("p", [1, 2], { name: "Recorded name" }), {
        Current: { p: metadata("Renamed parameter", "Hz") },
      }).name,
    ).toBe("Recorded name");
  });

  it("renders categorical values without inventing numeric ranges", () => {
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{}}
        scanParameters={[
          scan("mode", ["A, B", "", "C"]),
          scan("enabled", [false, true]),
        ]}
      />,
    );
    expect(html).toContain("&quot;A, B&quot;, &quot;&quot;, &quot;C&quot;");
    expect(html).toContain("false, true");
    expect(html).not.toContain(">Min</dt>");
    expect(html).toContain(">Unavailable</dd>");
  });

  it("retains axis numbering when realtime axes are omitted", () => {
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{}}
        scanParameters={[
          scan("Real Time", [], { realtime: true }),
          scan("p", [1, 2], { id: 2 }),
        ]}
      />,
    );
    expect(html).not.toContain('aria-label="Scan 1"');
    expect(html).toContain('aria-label="Scan 2"');
  });

  it("handles non-finite and overflowing numeric ranges without misleading spacing", () => {
    expect(scanBounds([NaN, 1])).toBeNull();
    expect(scanBounds([Infinity, 1])).toBeNull();
    expect(resultScanSpacing([-1e308, 1e308]).step).toBe("Unavailable");
    const html = renderToStaticMarkup(
      <ResultScanParameters
        parameters={{}}
        scanParameters={[scan("p", [-1e308, 1e308])]}
      />,
    );
    expect(html).toContain(">0</dd>");
    expect(html).not.toContain(">Infinity</dd>");
  });

  it("does not mutate the saved acquisition order", () => {
    const values = [5, 1, 3, 2, 4];
    resultScanSpacing(values);
    expect(values).toEqual([5, 1, 3, 2, 4]);
  });
});
