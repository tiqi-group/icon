import { ExperimentMetadata, ParameterValueType } from "../types/ExperimentMetadata";
import { ScanParameter } from "../types/ScanParameter";
import {
  experimentIdToNamespace,
  getExperimentNameFromExperimentId,
} from "./experimentUtils";

/** Saved backend values can also contain boolean and enum parameters. */
export type SavedScanParameter = Omit<ScanParameter, "scan_values"> & {
  scan_values: ParameterValueType[];
};

export const resultScanKey = (scan: SavedScanParameter): string =>
  scan.device
    ? `Device(${scan.device.name}) ${scan.variable_id}`
    : scan.device_id != null
      ? `Device(${scan.device_id}) ${scan.variable_id}`
      : scan.variable_id;

/** Submitted bounds, independent of acquisition order and the live scan editor. */
export function scanBounds(
  values: readonly ParameterValueType[],
): [number, number] | null {
  if (
    !values.length ||
    !values.every((value) => typeof value === "number" && Number.isFinite(value))
  )
    return null;
  let min = Infinity;
  let max = -Infinity;
  for (const value of values as number[]) {
    min = Math.min(min, value);
    max = Math.max(max, value);
  }
  return [min, max];
}

function identifierField(id: string, field: string): string | undefined {
  const match = id.match(
    new RegExp(`(?:^|\\s)${field}=(?:'((?:\\\\.|[^'\\\\])*)'|"((?:\\\\.|[^"\\\\])*)")`),
  );
  return (match?.[1] ?? match?.[2])?.replace(/\\([\\'"])/g, "$1");
}

export function resultScanIdentity(
  scan: SavedScanParameter,
  parameters: ExperimentMetadata["parameters"],
  experimentId?: string,
) {
  const key = resultScanKey(scan);
  const group = Object.entries(parameters).find(([, entries]) =>
    Object.hasOwn(entries, key),
  );
  const metadata = group?.[1][key];
  const isDevice = scan.device != null || scan.device_id != null;
  const namespace = isDevice
    ? "Devices"
    : (identifierField(scan.variable_id, "namespace") ??
      (group && experimentId ? experimentIdToNamespace(experimentId) : "Not recorded"));
  const namespaceLabel = namespace.endsWith(".globals.global_parameters")
    ? "Global Parameters"
    : experimentId && namespace === experimentIdToNamespace(experimentId)
      ? getExperimentNameFromExperimentId(experimentId)
      : (namespace.split(".").at(-1) ?? namespace);
  const savedGroup = identifierField(scan.variable_id, "parameter_group");
  return {
    namespace,
    namespaceLabel,
    groupLabel: isDevice ? "Device Name" : "Display Group",
    group: isDevice
      ? (scan.device?.name ?? `Device ${scan.device_id}`)
      : (group?.[0] ?? savedGroup ?? "Not recorded"),
    groupFromIdentifier: !isDevice && !group && !!savedGroup,
    name:
      scan.name ||
      metadata?.display_name ||
      identifierField(scan.variable_id, "name") ||
      scan.variable_id,
    unit: metadata?.unit,
  };
}

/** Derive spacing from saved points; never claim a constant step for irregular scans. */
export function resultScanSpacing(values: readonly ParameterValueType[]) {
  const bounds = scanBounds(values);
  if (!bounds) return { span: "Unavailable", step: "Unavailable", reordered: false };
  const span = bounds[1] - bounds[0];
  if (!Number.isFinite(span))
    return { span: "Unavailable", step: "Unavailable", reordered: false };
  const numeric = values as number[];
  const sorted = [...new Set(numeric)].sort((a, b) => a - b);
  if (sorted.length === 1) return { span: "0", step: "No step", reordered: false };
  const step = span / (sorted.length - 1);
  // Allow only floating-point reconstruction noise when checking a uniform grid.
  const tolerance = Math.min(
    Math.abs(step) * 1e-6,
    Math.max(
      Number.EPSILON * Math.max(Math.abs(bounds[0]), Math.abs(bounds[1])) * 4,
      Math.abs(step) * 1e-9,
    ),
  );
  const uniform = sorted.every(
    (value, i) => Math.abs(value - (sorted[0] + i * step)) <= tolerance,
  );
  if (!uniform) return { span: String(span), step: "Variable", reordered: false };
  const orderedStep = (numeric.at(-1)! - numeric[0]) / (numeric.length - 1);
  const ordered =
    orderedStep !== 0 &&
    numeric.every(
      (value, i) => Math.abs(value - (numeric[0] + i * orderedStep)) <= tolerance,
    );
  return {
    span: String(span),
    step: String(ordered ? orderedStep : step),
    reordered: !ordered,
  };
}
