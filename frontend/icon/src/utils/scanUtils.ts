import { GroupsByNamespace } from "../hooks/useParameterDisplayGroups";
import { Store } from "../stores/parmeterStore";
import { DeviceInfo } from "../types/DeviceInfo";
import { ParameterMetadata } from "../types/ExperimentMetadata";
import { ScanParameterInfo } from "../types/ScanParameterInfo";

export interface ScanParameterBounds {
  min: number | null;
  max: number | null;
}

/**
 * Refreshes Span-mode parameters' start/stop from each parameter's current live
 * value, keeping the remembered span. Span mode never stores a "center" — it's
 * always the parameter's live value, looked up here fresh (typically right before
 * submitting a job) rather than reused from whenever the span was last edited.
 *
 * Parameters not in Span mode, or whose live value isn't known/numeric, are
 * returned unchanged.
 *
 * @param parameters - The scan parameters to refresh.
 * @param parameterStore - Store to read live parameter values from.
 * @returns A new parameters array with Span-mode entries re-centred.
 */
export const refreshSpanCenterParameters = (
  parameters: ScanParameterInfo[],
  parameterStore: Pick<Store, "get"> | null,
): ScanParameterInfo[] =>
  parameters.map((param) => {
    if ((param.generation.inputMode ?? "startStop") !== "spanCenter") return param;
    const liveValue = parameterStore?.get(param.id);
    if (typeof liveValue !== "number") return param;
    const span = Math.abs(param.generation.stop - param.generation.start);
    return {
      ...param,
      generation: {
        ...param.generation,
        start: liveValue - span / 2,
        stop: liveValue + span / 2,
      },
    };
  });

const getScanParameterMetadata = (
  param: ScanParameterInfo,
  parameterDisplayGroups: GroupsByNamespace,
): ParameterMetadata | undefined => {
  if (
    !param.namespace ||
    !param.deviceNameOrDisplayGroup ||
    param.namespace === "Devices" ||
    param.namespace === "Real Time"
  ) {
    return undefined;
  }
  return parameterDisplayGroups[
    `${param.namespace} (${param.deviceNameOrDisplayGroup})`
  ]?.[param.id];
};

/**
 * Looks up the allowed value range of a scan parameter from the display group
 * metadata (as provided by the experiment library).
 *
 * Device and realtime parameters carry no range metadata, so their bounds are null.
 *
 * @param param - The scan parameter to look up.
 * @param parameterDisplayGroups - Display group metadata keyed by "namespace (group)".
 * @returns The parameter's min/max bounds, null when unbounded or unknown.
 */
export const getScanParameterBounds = (
  param: ScanParameterInfo,
  parameterDisplayGroups: GroupsByNamespace,
): ScanParameterBounds => {
  const metadata = getScanParameterMetadata(param, parameterDisplayGroups);
  return {
    min: metadata?.min_value ?? null,
    max: metadata?.max_value ?? null,
  };
};

/** Returns a scan parameter's display name, falling back to its ID. */
export const getScanParameterDisplayName = (
  param: ScanParameterInfo,
  parameterDisplayGroups: GroupsByNamespace,
): string =>
  getScanParameterMetadata(param, parameterDisplayGroups)?.display_name ?? param.id;

export const clampToBounds = (value: number, bounds: ScanParameterBounds): number => {
  if (bounds.min !== null && value < bounds.min) return bounds.min;
  if (bounds.max !== null && value > bounds.max) return bounds.max;
  return value;
};

/**
 * Constructs a unique key for identifying a scanned parameter.
 *
 * For experiment parameters, this returns the parameter ID as-is.
 * For device parameters (i.e., when namespace is "Devices"), it returns
 * the full access path used to uniquely identify the parameter, including
 * the device name.
 *
 * Example:
 *   makeScannedParamKey("laser_power", "Devices", "Laser A")
 *   → 'devices.device_proxies["Laser A"].laser_power'
 *
 * @param id - The parameter ID.
 * @param namespace - The parameter's namespace (e.g., "Devices" or an experiment namespace).
 * @param deviceNameOrDisplayGroup - Device name (for device parameters) or display group name.
 * @returns A string key uniquely identifying the scanned parameter.
 */
export const makeScannedParamKey = (
  id: string,
  namespace: string,
  deviceNameOrDisplayGroup: string,
): string =>
  namespace === "Devices"
    ? `devices.device_proxies["${deviceNameOrDisplayGroup}"].${id}`
    : id;

/**
 * Inverse of makeScannedParamKey: recovers the bare parameter id from a scanned
 * key. For device parameters it strips the `devices.device_proxies["<device>"].`
 * prefix; for other namespaces the key is already the bare id.
 *
 * @param scannedKey - The full scanned parameter key (as built by makeScannedParamKey).
 * @param namespace - The parameter's namespace (e.g., "Devices").
 * @param deviceNameOrDisplayGroup - Device name (for device parameters) or display group name.
 * @returns The bare parameter id.
 */
export const extractScannedParamId = (
  scannedKey: string,
  namespace: string,
  deviceNameOrDisplayGroup: string,
): string => {
  if (namespace !== "Devices") return scannedKey;
  const prefix = `devices.device_proxies["${deviceNameOrDisplayGroup}"].`;
  return scannedKey.startsWith(prefix) ? scannedKey.slice(prefix.length) : scannedKey;
};

/**
 * Returns the index of a scanned parameter within the scanned parameters list.
 *
 * This function checks if the given `paramId` exists in the `scannedParams` array
 * and returns its index if found. If the parameter is not found, it returns null.
 *
 * @param paramId - The full key identifying the parameter (as generated by makeScannedParamKey).
 * @param scannedParams - The list of scanned parameter keys.
 * @returns The index of the parameter in the scan list, or null if not found.
 */
export const getScanIndex = (
  paramId: string,
  scannedParams: string[],
): number | null => {
  const index = scannedParams.indexOf(paramId);
  return index !== -1 ? index : null;
};

/**
 * Determines if a parameter type can be scanned with numeric ranges.
 *
 * @param paramId - The parameter ID string containing type information.
 * @returns True if the parameter can be scanned (numeric types), false otherwise.
 */
export function isScannableParameterType(paramId: string): boolean {
  if (paramId.includes("param_type='ParameterTypes.BOOLEAN'")) {
    return false;
  }

  if (paramId.includes("param_type='ParameterTypes.ENUM'")) {
    return false;
  }

  return true;
}

export interface ScanParameterOption {
  displayName: string;
  min: number | null;
  max: number | null;
}

/**
 * Lists the scannable parameters of one display group, or of one device when
 * `namespace` is "Devices", keyed by the id stored in `ScanParameterInfo.id`.
 */
export const getScanParameterOptions = (
  namespace: string,
  deviceNameOrDisplayGroup: string,
  parameterDisplayGroups: GroupsByNamespace,
  devices: Record<string, Pick<DeviceInfo, "scannable_params">>,
): Record<string, ScanParameterOption> => {
  if (!namespace || !deviceNameOrDisplayGroup) return {};

  if (namespace === "Devices") {
    const device = devices[deviceNameOrDisplayGroup];
    if (!device) return {};

    const prefixLength = makeScannedParamKey(
      "",
      namespace,
      deviceNameOrDisplayGroup,
    ).length;

    return Object.fromEntries(
      device.scannable_params.map((paramId) => {
        const shortId = paramId.slice(prefixLength);
        return [shortId, { displayName: shortId, min: null, max: null }];
      }),
    );
  }

  const group =
    parameterDisplayGroups[`${namespace} (${deviceNameOrDisplayGroup})`] || {};

  return Object.fromEntries(
    Object.entries(group)
      .filter(([paramId, meta]) => isScannableParameterType(paramId) && !meta.read_only)
      .map(([paramId, meta]) => [
        paramId,
        { displayName: meta.display_name, min: meta.min_value, max: meta.max_value },
      ]),
  );
};

export interface ScanParameterSearchOption {
  id: string;
  namespace: string;
  deviceNameOrDisplayGroup: string;
  displayName: string;
  groupLabel: string;
  searchText: string;
}

// Every parameter id repeats these, so matching them would hit everything.
const UNSEARCHED_ID_SPECIFIERS = ["namespace", "parameter_group", "param_type"];

const getIdSpecifierValues = (paramId: string): string[] =>
  [...paramId.matchAll(/(\w+)='([^']*)'/g)]
    .filter(([, key]) => !UNSEARCHED_ID_SPECIFIERS.includes(key))
    .map(([, , value]) => value);

/**
 * Flattens all scannable parameters of the given sources (namespace to display
 * groups or device names) into one list, in source and group order.
 */
export const getScanParameterSearchOptions = (
  sources: Record<string, string[]>,
  parameterDisplayGroups: GroupsByNamespace,
  devices: Record<string, Pick<DeviceInfo, "scannable_params">>,
  getNamespaceLabel: (namespace: string) => string,
): ScanParameterSearchOption[] =>
  Object.entries(sources).flatMap(([namespace, groups]) =>
    groups.flatMap((group) =>
      Object.entries(
        getScanParameterOptions(namespace, group, parameterDisplayGroups, devices),
      ).map(([id, { displayName }]) => {
        const namespaceLabel = getNamespaceLabel(namespace);
        const idTerms = namespace === "Devices" ? [] : getIdSpecifierValues(id);
        return {
          id,
          namespace,
          deviceNameOrDisplayGroup: group,
          displayName,
          groupLabel: `${namespaceLabel} / ${group}`,
          searchText: [displayName, group, namespaceLabel, ...idTerms]
            .join("\n")
            .toLowerCase(),
        };
      }),
    ),
  );

/**
 * Returns the options containing every whitespace-separated word of `query`.
 * Exact, then prefix, then other display name matches come first; otherwise
 * options keep their list order.
 */
export const searchScanParameterOptions = (
  options: ScanParameterSearchOption[],
  query: string,
): ScanParameterSearchOption[] => {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const phrase = words.join(" ");
  const rank = (option: ScanParameterSearchOption): number => {
    const name = option.displayName.toLowerCase();
    if (name === phrase) return 0;
    if (name.startsWith(phrase)) return 1;
    if (words.every((word) => name.includes(word))) return 2;
    return 3;
  };
  if (words.length === 0) return [];
  return options
    .filter((option) => words.every((word) => option.searchText.includes(word)))
    .map((option) => ({ option, rank: rank(option) }))
    .sort((a, b) => a.rank - b.rank)
    .map(({ option }) => option);
};
