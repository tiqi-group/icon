import { useContext, useMemo } from "react";
import {
  IconButton,
  TextField,
  Checkbox,
  FormControlLabel,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
} from "@mui/material";
import DeleteIcon from "@mui/icons-material/Delete";
import { useScanContext } from "../../hooks/useScanContext";
import {
  ScanParameterInfo,
  ScanPattern,
  scanPatterns,
} from "../../types/ScanParameterInfo";
import { ParameterDisplayGroupsContext } from "../../contexts/ParameterDisplayGroupsContext";
import { DeviceInfoContext } from "../../contexts/DeviceInfoContext";

const generateScanValues = (
  start: number,
  stop: number,
  points: number,
  pattern: ScanPattern,
) => {
  const linspace = (n: number) =>
    Array.from({ length: n }, (_, i) => start + (i * (stop - start)) / (n - 1));

  switch (pattern) {
    case "linear":
      return linspace(points);
    case "scatter":
      return linspace(points).sort(() => Math.random() - 0.5);
    case "centred": {
      const base = linspace(points);
      const mid = Math.floor((points - 1) / 2);
      const order = [mid];
      for (let k = 1; order.length < points; k++) {
        if (mid - k >= 0) order.push(mid - k);
        if (mid + k < points) order.push(mid + k);
      }
      return order.map((i) => base[i]);
    }
    case "forwardReverse": {
      const base = linspace(points);
      return [...base, ...base.reverse()];
    }
  }
};

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

export const ParameterCard = ({
  param,
  index,
}: {
  param: ScanParameterInfo;
  index: number;
}) => {
  const { dispatchScanInfoStateUpdate } = useScanContext();

  const { parameterDisplayGroups, parameterNamespaceToDisplayGroups } = useContext(
    ParameterDisplayGroupsContext,
  );
  const deviceInfo = useContext(DeviceInfoContext);
  const parameterSources: Record<string, string[]> = {
    ...parameterNamespaceToDisplayGroups,
    Devices: Object.keys(deviceInfo),
  };

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
      Object.entries(group).map(([paramId, meta]) => [
        paramId,
        {
          displayName: meta.display_name,
          min: meta.min_value,
          max: meta.max_value,
        },
      ]),
    );
  }, [param, parameterDisplayGroups, deviceInfo]);

  const pattern = param.generation.pattern ?? "linear";

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
              dispatchScanInfoStateUpdate({
                type: "UPDATE_PARAMETER",
                index,
                payload: {
                  id: "",
                  deviceNameOrDisplayGroup: "",
                  namespace: e.target.value,
                },
              });
            }}
            renderValue={(selected) => {
              const truncated =
                selected.length > 30 ? selected.slice(0, 30) + "..." : selected;
              return truncated;
            }}
          >
            {Object.keys(parameterSources).map((namespace) => (
              <MenuItem key={namespace} value={namespace}>
                {namespace}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton
          onClick={() =>
            dispatchScanInfoStateUpdate({ type: "REMOVE_PARAMETER", index })
          }
        >
          <DeleteIcon />
        </IconButton>
      </div>
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
                id: "",
                deviceNameOrDisplayGroup: e.target.value,
              },
            });
          }}
          renderValue={(selected) => {
            const truncated =
              selected.length > 30 ? selected.slice(0, 30) + "..." : selected;
            return truncated;
          }}
        >
          {(parameterSources[param.namespace!] ?? []).map((groupOrDevice: string) => (
            <MenuItem key={groupOrDevice} value={groupOrDevice}>
              {groupOrDevice}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <FormControl
        fullWidth
        size="small"
        disabled={Object.keys(parameterOptions).length === 0}
      >
        <InputLabel>Parameter</InputLabel>
        <Select
          label="Parameter"
          value={param.id}
          title={param.id}
          onChange={(e) => {
            dispatchScanInfoStateUpdate({
              type: "UPDATE_PARAMETER",
              index,
              payload: { id: e.target.value },
            });
          }}
          renderValue={(value) => {
            const selectedDisplayName = parameterOptions[value]?.displayName;
            if (selectedDisplayName === undefined) return value;
            return selectedDisplayName.length > 30
              ? selectedDisplayName.slice(0, 30) + "..."
              : selectedDisplayName;
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
        <TextField
          required
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
                values: generateScanValues(
                  Number(e.target.value),
                  param.generation.stop,
                  param.generation.points,
                  pattern,
                ),
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
                values: generateScanValues(
                  param.generation.start,
                  Number(e.target.value),
                  param.generation.points,
                  pattern,
                ),
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
                values: generateScanValues(
                  param.generation.start,
                  param.generation.stop,
                  Number(e.target.value),
                  pattern,
                ),
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
          label="Scan pattern"
          value={pattern}
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
    </div>
  );
};
