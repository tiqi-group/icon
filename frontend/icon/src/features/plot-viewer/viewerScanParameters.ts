import type { ExperimentData } from "../../types/ExperimentData";
import type { ScanParameter } from "../../types/ScanParameter";

type ScanMaps = ExperimentData["scan_parameters"];

function names(parameter: ScanParameter): string[] {
  return [...new Set([parameter.variable_id, parameter.name])];
}

function qualified(parameter: ScanParameter, name: string): string | undefined {
  const device = parameter.device;
  // The scheduler's device object is authoritative; never infer a device by
  // stripping an arbitrary Device(...) prefix from an incoming identity.
  return device && (parameter.device_id == null || parameter.device_id === device.id)
    ? `Device(${device.name}) ${name}`
    : undefined;
}

/** Unique viewer key; device-local variables can share the same unqualified ID. */
export function viewerScanParameterKey(
  parameter: ScanParameter,
  parameters: ScanParameter[],
): string {
  return parameters.filter(
    (candidate) => candidate.variable_id === parameter.variable_id,
  ).length === 1
    ? parameter.variable_id
    : (qualified(parameter, parameter.variable_id) ?? `axis:${parameter.id}`);
}

/**
 * Snapshot axes use variable IDs; live axes may use Device(name) + variable ID.
 * Reconcile only aliases claimed by exactly one scheduled axis. Keep each map
 * immutable so Hold, pending snapshot replay and reconnect can share raw data.
 */
export function resolveViewerScanMaps(
  scanMaps: ScanMaps,
  parameters: ScanParameter[],
): ScanMaps[string][] {
  const claims = new Map<string, number>();
  for (const parameter of parameters) {
    if (parameter.realtime) continue;
    const aliases = new Set(
      names(parameter).flatMap((name) => {
        const full = qualified(parameter, name);
        return full ? [name, full] : [name];
      }),
    );
    for (const alias of aliases) claims.set(alias, (claims.get(alias) ?? 0) + 1);
  }
  return parameters.map((parameter) => {
    if (parameter.realtime) return scanMaps.timestamp ?? {};
    // Preserve the existing variable-ID-before-display-name contract. Qualified
    // values override the corresponding snapshot index, just as live replay does.
    for (const name of names(parameter)) {
      const full = qualified(parameter, name);
      const aliases = [name, full].filter(
        (alias): alias is string =>
          alias !== undefined &&
          claims.get(alias) === 1 &&
          Object.hasOwn(scanMaps, alias),
      );
      if (aliases.length)
        return Object.assign({}, ...aliases.map((alias) => scanMaps[alias]));
    }
    return {};
  });
}
