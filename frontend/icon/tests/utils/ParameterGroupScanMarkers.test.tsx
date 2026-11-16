import { renderToStaticMarkup } from "react-dom/server";
import { ParameterGroupDisplay } from "../../src/components/ParameterGroupDisplay";
import { useScanContext } from "../../src/hooks/useScanContext";

// The existing widgets use default React imports; provide their CJS test interop.
jest.mock("react", () => {
  const react = jest.requireActual("react");
  return { __esModule: true, ...react, default: react };
});

jest.mock("../../src/components/parameterComponents/Number.css", () => ({}));
jest.mock("../../src/hooks/useParameter", () => ({
  useParameter: () => [777, jest.fn()],
}));
jest.mock("../../src/hooks/useScanContext", () => ({
  useScanContext: jest.fn(() => ({
    scannedParamKeys: [],
    handleRightClick: jest.fn(),
  })),
}));
jest.mock("../../src/hooks/useResponsiveGridColumns", () => ({
  useResponsiveGridColumns: () => "repeat(2, 1fr)",
}));
jest.mock("../../src/socket", () => ({
  runMethod: jest.fn(),
  getValue: jest.fn(),
  updateValue: jest.fn(),
  socket: { on: jest.fn(), off: jest.fn() },
}));

const metadata = (name: string, value: number | boolean | string) => ({
  display_name: name,
  default_value: value,
  unit: "",
  min_value: null,
  max_value: null,
});
const parameters = {
  fixed: metadata("Fixed number", 99),
  zero: metadata("Zero", 1),
  enabled: metadata("Fixed boolean", true),
  mode: metadata("Fixed enum", "Manual"),
};
const values = Object.fromEntries(
  Object.entries({ fixed: 42, zero: 0, enabled: false, mode: "Auto" }).map(
    ([key, value]) => [key, { timestamp: "2026-11-07T10:00:00", value }],
  ),
);

describe("result scan markers", () => {
  it("keeps all fixed widgets identical to the original read-only renderer", () => {
    const original = renderToStaticMarkup(
      <ParameterGroupDisplay parameters={parameters} values={values} readOnly />,
    );
    const result = renderToStaticMarkup(
      <ParameterGroupDisplay
        parameters={parameters}
        values={values}
        readOnly
        readOnlyScanKeys={["p1", "p2"]}
      />,
    );
    expect(result).toBe(original);
    expect(result).toContain('value="42"');
    expect(result).toContain('value="0"');
    expect(result).toContain('value="Auto"');
    expect(result).toContain(">Off</button>");
  });

  it("keeps recorded values alongside numbered scan markers", () => {
    const result = renderToStaticMarkup(
      <ParameterGroupDisplay
        parameters={{
          ...parameters,
          p1: metadata("Parameter 1", 99),
          p2: metadata("Parameter 2", 88),
        }}
        values={{
          ...values,
          p1: { timestamp: "", value: 0.25 },
          p2: { timestamp: "", value: 0.75 },
        }}
        readOnly
        readOnlyScanKeys={["p1", "p2"]}
      />,
    );
    expect(result).toContain(">Scan 1</span>");
    expect(result).toContain(">Scan 2</span>");
    expect(result).toContain('title="Recorded parameter value"');
    expect(result).toContain(">0.25</span>");
    expect(result).toContain(">0.75</span>");
    expect(result).not.toContain(">777</span>");
    expect(result).toContain('value="42"');
    expect(result).toContain(">Off</button>");
  });

  it("preserves zero and full precision and does not substitute a missing recorded value", () => {
    const result = renderToStaticMarkup(
      <ParameterGroupDisplay
        parameters={{
          zero: metadata("Zero", 99),
          precise: metadata("Precise", 88),
          missing: metadata("Missing", 66),
        }}
        values={{
          zero: { timestamp: "", value: 0 },
          precise: { timestamp: "", value: 1.2345678901234567 },
        }}
        readOnly
        readOnlyScanKeys={["zero", "precise", "missing"]}
      />,
    );
    expect(result).toContain(">0</span>");
    expect(result).toContain(">1.2345678901234567</span>");
    expect(result).toContain(">Not recorded</span>");
    expect(result).not.toContain(">777</span>");
    expect(result).not.toContain(">66</span>");
  });

  it("uses saved job axes instead of the currently edited scan", () => {
    jest.mocked(useScanContext).mockReturnValueOnce({
      ...useScanContext(),
      scannedParamKeys: ["fixed"],
    });
    const result = renderToStaticMarkup(
      <ParameterGroupDisplay
        parameters={parameters}
        values={values}
        readOnly
        readOnlyScanKeys={[]}
      />,
    );
    expect(result).not.toContain("Scan parameter");
    expect(result).toContain('value="42"');
  });
});

it("preserves false and an empty string as recorded scan values", () => {
  const html = renderToStaticMarkup(
    <ParameterGroupDisplay
      parameters={{
        enabled: metadata("Enabled", true),
        mode: metadata("Mode", "Default"),
      }}
      values={{
        enabled: { timestamp: "", value: false },
        mode: { timestamp: "", value: "" },
      }}
      readOnly
      readOnlyScanKeys={["enabled", "mode"]}
    />,
  );
  expect(html).toContain(">false</span>");
  expect(html).not.toContain("Not recorded");
  expect(html).not.toContain("Default");
});
