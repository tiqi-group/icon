import DeleteIcon from "@mui/icons-material/Delete";
import {
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Select,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import { useContext, useMemo } from "react";
import { ParameterStoreContext } from "../../contexts/ParameterStoreContext";
import { DeviceInfoContext } from "../../contexts/DeviceInfoContext";
import { ExperimentsContext } from "../../contexts/ExperimentsContext";
import { ParameterDisplayGroupsContext } from "../../contexts/ParameterDisplayGroupsContext";
import { useScanContext } from "../../hooks/useScanContext";
import {
  getExperimentNameFromExperimentId,
  experimentIdToNamespace,
} from "../../utils/experimentUtils";
import {
  ScanInputMode,
  ScanParameterInfo,
  ScanPattern,
  scanPatterns,
} from "../../types/ScanParameterInfo";
import { isScannableParameterType } from "../../utils/scanUtils";

const renderPatternLabel = (pattern: ScanPattern): string => {
  switch (pattern) {
    case "linear":
      return "Linear";
    case "scatter":
      return "Scatter";
    case "centred":
      return "Centred";
    case "forwardReverse":
      return "Forward and reverse";
  }
};

const getDisplayNameFromNamespace = (namespace: string): string => {
  if (namespace.endsWith(".globals.global_parameters")) return "Global Parameters";
  const parts = namespace.split(".");
  return parts[parts.length - 1];
};

const truncateDisplayName = (displayName: string): string => {
  return displayName.length > 30 ? displayName.slice(0, 30) + "..." : displayName;
};

export const ParameterCard = ({
  param,
  index,
  showRealtime,
}: {
  param: ScanParameterInfo;
  index: number;
  showRealtime: boolean;
}) => {
  const { scanInfoState, dispatchScanInfoStateUpdate, experimentId } = useScanContext();

  const { parameterDisplayGroups, parameterNamespaceToDisplayGroups } = useContext(
    ParameterDisplayGroupsContext,
  );
  const deviceInfo = useContext(DeviceInfoContext);
  const experiments = useContext(ExperimentsContext);
  const parameterStore = useContext(ParameterStoreContext);

  // Create a mapping from namespace to experiment display name
  const namespaceToDisplayName: Record<string, string> = Object.fromEntries(
    Object.keys(experiments).map(expId => [
      experimentIdToNamespace(expId),
      getExperimentNameFromExperimentId(expId)
    ])
  );

  // Filter namespaces to include only relevant ones
  const filteredNamespaces = useMemo(() => {
    return Object.fromEntries(
      Object.entries(parameterNamespaceToDisplayGroups).filter(([namespace]) =>
        namespace.endsWith(".globals.global_parameters") ||
        (experimentId && namespace === experimentIdToNamespace(experimentId))
      )
    );
  }, [parameterNamespaceToDisplayGroups, experimentId]);

  const ordinaryParameterSources: Record<string, string[]> = {
    ...filteredNamespaces,
    Devices: Object.keys(deviceInfo),
  };
  const parameterSources: Record<string, string[]> = showRealtime
    ? {
        ...ordinaryParameterSources,
        "Real Time": ["Real Time"],
      }
    : ordinaryParameterSources;

  const parameterOptions = useMemo(() => {
    if (!param.namespace || !param.deviceNameOrDisplayGroup) return {};

    const groupKey = param.deviceNameOrDisplayGroup;

    if (param.namespace === "Devices") {
      const device = deviceInfo[groupKey];
      if (!device) return {};

      const prefix = `devices.device_proxies["${groupKey}"].`;
      const prefixLength = prefix.length;

      return Object.fromEntries(
        device.scannable_params.map((paramId) => {
          const shortId = paramId.slice(prefixLength);
          return [
            shortId,
            {
              displayName: shortId,
              min: null,
              max: null,
            },
          ];
        }),
      );
    }

    const key = `${param.namespace} (${groupKey})`;
    const group = parameterDisplayGroups[key] || {};

    return Object.fromEntries(
      Object.entries(group)
        .filter(
          ([paramId, meta]) => isScannableParameterType(paramId) && !meta.read_only,
        )
        .map(([paramId, meta]) => [
          paramId,
          {
            displayName: meta.display_name,
            min: meta.min_value,
            max: meta.max_value,
          },
        ]),
    );
  }, [param, parameterDisplayGroups, deviceInfo]);

  const inputMode: ScanInputMode = param.generation.inputMode ?? "startStop";

  // Derived quantities for span/center mode. Center and span are reconstructed from
  // start/stop on every render, so round away the floating-point reconstruction
  // noise (e.g. 0.015099999999996783 for a typed 0.0151) well above the ~16-digit
  // float precision but far below any physically meaningful digit.
  const roundFloatNoise = (value: number) => Number(value.toPrecision(12));
  const center = roundFloatNoise((param.generation.start + param.generation.stop) / 2);
  const span = roundFloatNoise(param.generation.stop - param.generation.start);

  const handleInputModeChange = (
    _: React.MouseEvent,
    newMode: ScanInputMode | null,
  ) => {
    if (!newMode || newMode === inputMode) return;

    // Each mode remembers its own start/stop/points/pattern independently: editing
    // fields in one mode must never change what the other mode shows. Toggling swaps
    // the active quadruple with the snapshot stashed for the mode being entered (or
    // keeps the current one, unchanged, the first time that other mode is visited).
    const currentModeSpec = {
      start: param.generation.start,
      stop: param.generation.stop,
      points: param.generation.points,
      pattern: param.generation.pattern,
    };
    const restoredModeSpec = param.generation.otherModeSpec ?? currentModeSpec;

    dispatchScanInfoStateUpdate({
      type: "UPDATE_PARAMETER",
      index,
      payload: {
        generation: {
          ...restoredModeSpec,
          inputMode: newMode,
          otherModeSpec: currentModeSpec,
        },
      },
    });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <FormControl fullWidth size="small">
          <InputLabel>Namespace</InputLabel>
          <Select
            label="Namespace"
            title={param.namespace}
            value={param.namespace}
            onChange={(e) => {
              const isRealtime = e.target.value === "Real Time";
              dispatchScanInfoStateUpdate({
                type: "UPDATE_PARAMETER",
                index,
                payload: {
                  id: isRealtime ? "Real Time" : undefined,
                  namespace: e.target.value,
                  n_scan_points: isRealtime ? 0 : undefined,
                },
              });
            }}
            renderValue={(selected) => {
              const displayName = selected === "Devices" || selected === "Real Time"
                ? selected
                : (namespaceToDisplayName[selected] || getDisplayNameFromNamespace(selected));
              return truncateDisplayName(displayName);
            }}
          >
            {Object.keys(parameterSources).map((namespace) => {
              const displayName = namespace === "Devices" || namespace === "Real Time"
                ? namespace
                : (namespaceToDisplayName[namespace] || getDisplayNameFromNamespace(namespace));
              return (
                <MenuItem key={namespace} value={namespace}>
                  {displayName}
                </MenuItem>
              );
            })}
          </Select>
        </FormControl>
        {scanInfoState.parameters.length > 1 && (
          <IconButton
            onClick={() =>
              dispatchScanInfoStateUpdate({ type: "REMOVE_PARAMETER", index })
            }
          >
            <DeleteIcon />
          </IconButton>
        )}
      </div>
      {param.namespace !== "Real Time" ? (
        <>
          <FormControl fullWidth size="small" disabled={!param.namespace}>
            <InputLabel>
              {param.namespace === "Devices" ? "Device Name" : "Display Group"}
            </InputLabel>
            <Select
              label={param.namespace === "Devices" ? "Device Name" : "Display Group"}
              value={param.deviceNameOrDisplayGroup}
              onChange={(e) => {
                dispatchScanInfoStateUpdate({
                  type: "UPDATE_PARAMETER",
                  index,
                  payload: {
                    deviceNameOrDisplayGroup: e.target.value,
                  },
                });
              }}
              renderValue={(selected) => truncateDisplayName(selected)}
            >
              {(parameterSources[param.namespace!] ?? []).map(
                (groupOrDevice: string) => (
                  <MenuItem key={groupOrDevice} value={groupOrDevice}>
                    {groupOrDevice}
                  </MenuItem>
                ),
              )}
            </Select>
          </FormControl>

          <FormControl
            fullWidth
            size="small"
            disabled={Object.keys(parameterOptions).length === 0}
          >
            <InputLabel>
              {param.namespace &&
              param.deviceNameOrDisplayGroup &&
              Object.keys(parameterOptions).length === 0
                ? "No scannable Parameters"
                : "Parameter"}
            </InputLabel>
            <Select
              label="Parameter"
              value={param.id}
              title={param.id}
              onChange={(e) => {
                const newParamId = e.target.value;

                if (inputMode === "spanCenter") {
                  // Restore the new parameter's own remembered settings, re-centred
                  // on its live value (if numeric) while keeping its own span.
                  const rawValue = parameterStore?.get(newParamId);
                  const recenterOn =
                    typeof rawValue === "number" ? rawValue : undefined;
                  dispatchScanInfoStateUpdate({
                    type: "UPDATE_PARAMETER",
                    index,
                    payload: { id: newParamId },
                    recenterOn,
                  });
                } else {
                  dispatchScanInfoStateUpdate({
                    type: "UPDATE_PARAMETER",
                    index,
                    payload: { id: newParamId },
                  });
                }
              }}
              renderValue={(value) => {
                const selectedDisplayName = parameterOptions[value]?.displayName;
                if (selectedDisplayName === undefined) return value;
                return truncateDisplayName(selectedDisplayName);
              }}
            >
              {Object.entries(parameterOptions).map(([paramId, metadata]) => (
                <MenuItem key={paramId} value={paramId} title={paramId}>
                  {metadata.displayName}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <ToggleButtonGroup
              value={inputMode}
              exclusive
              size="small"
              fullWidth
              disabled={!param.id}
              onChange={handleInputModeChange}
            >
              <ToggleButton value="startStop" sx={{ textTransform: "none" }}>
                Start / Stop
              </ToggleButton>
              <ToggleButton value="spanCenter" sx={{ textTransform: "none" }}>
                Center / Span
              </ToggleButton>
            </ToggleButtonGroup>

            {inputMode === "spanCenter" ? (
              <>
                <TextField
                  required
                  disabled={!param.id}
                  label="Center"
                  size="small"
                  type="number"
                  fullWidth
                  value={center}
                  onChange={(e) => {
                    const newCenter = Number(e.target.value);
                    dispatchScanInfoStateUpdate({
                      type: "UPDATE_PARAMETER",
                      index,
                      payload: {
                        generation: {
                          ...param.generation,
                          start: newCenter - span / 2,
                          stop: newCenter + span / 2,
                        },
                      },
                    });
                  }}
                  variant="outlined"
                  slotProps={{
                    input: {
                      inputProps: {
                        min: parameterOptions[param.id]?.min,
                        max: parameterOptions[param.id]?.max,
                      },
                    },
                  }}
                />
                <TextField
                  required
                  disabled={!param.id}
                  label="Span"
                  size="small"
                  type="number"
                  fullWidth
                  value={Math.abs(span)}
                  onChange={(e) => {
                    const newSpan = Math.abs(Number(e.target.value));
                    dispatchScanInfoStateUpdate({
                      type: "UPDATE_PARAMETER",
                      index,
                      payload: {
                        generation: {
                          ...param.generation,
                          start: center - newSpan / 2,
                          stop: center + newSpan / 2,
                        },
                      },
                    });
                  }}
                  variant="outlined"
                  slotProps={{
                    input: { inputProps: { min: 0 } },
                  }}
                />
              </>
            ) : (
              <>
                <TextField
                  required
                  disabled={!param.id}
                  label="Start"
                  size="small"
                  type="number"
                  fullWidth
                  value={param.generation.start}
                  onChange={(e) =>
                    dispatchScanInfoStateUpdate({
                      type: "UPDATE_PARAMETER",
                      index,
                      payload: {
                        generation: {
                          ...param.generation,
                          start: Number(e.target.value),
                        },
                      },
                    })
                  }
                  variant="outlined"
                  slotProps={{
                    input: {
                      inputProps: {
                        min: parameterOptions[param.id]?.min,
                        max: parameterOptions[param.id]?.max,
                      },
                    },
                  }}
                />
                <TextField
                  required
                  disabled={!param.id}
                  label="Stop"
                  size="small"
                  type="number"
                  fullWidth
                  value={param.generation.stop}
                  onChange={(e) =>
                    dispatchScanInfoStateUpdate({
                      type: "UPDATE_PARAMETER",
                      index,
                      payload: {
                        generation: {
                          ...param.generation,
                          stop: Number(e.target.value),
                        },
                      },
                    })
                  }
                  variant="outlined"
                  slotProps={{
                    input: {
                      inputProps: {
                        min: parameterOptions[param.id]?.min,
                        max: parameterOptions[param.id]?.max,
                      },
                    },
                  }}
                />
              </>
            )}

            <TextField
              required
              disabled={!param.id}
              label="Points"
              size="small"
              type="number"
              fullWidth
              error={param.generation.points < 1}
              value={param.generation.points}
              onChange={(e) =>
                dispatchScanInfoStateUpdate({
                  type: "UPDATE_PARAMETER",
                  index,
                  payload: {
                    generation: {
                      ...param.generation,
                      points: Number(e.target.value),
                    },
                  },
                })
              }
              variant="outlined"
              slotProps={{
                input: {
                  inputProps: {
                    min: 1,
                  },
                },
              }}
            />
          </div>
          <FormControl fullWidth size="small">
            <InputLabel>Scan pattern</InputLabel>
            <Select
              disabled={!param.id}
              label="Scan pattern"
              value={param.generation.pattern}
              onChange={(e) => {
                dispatchScanInfoStateUpdate({
                  type: "UPDATE_PARAMETER",
                  index: index!,
                  payload: {
                    generation: {
                      ...param.generation,
                      pattern: e.target.value as ScanPattern,
                    },
                  },
                });
              }}
              renderValue={(selected) => renderPatternLabel(selected as ScanPattern)}
            >
              {scanPatterns.map((pattern) => (
                <MenuItem key={pattern} value={pattern}>
                  {renderPatternLabel(pattern)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </>
      ) : (
        <TextField
          label="Number of Scan Points"
          size="small"
          fullWidth
          placeholder="Continuous"
          inputMode="numeric"
          value={param.n_scan_points ? param.n_scan_points : ""}
          onChange={(e) => {
            const parsed = parseInt(e.target.value, 10);
            dispatchScanInfoStateUpdate({
              type: "UPDATE_PARAMETER",
              index,
              payload: {
                n_scan_points: isNaN(parsed) ? 0 : parsed,
              },
            });
          }}
          variant="outlined"
        />
      )}
    </div>
  );
};
