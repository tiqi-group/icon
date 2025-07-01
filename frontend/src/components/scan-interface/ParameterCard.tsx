import { useContext, useMemo } from "react";
import {
  Box,
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
import { ScanParameterInfo } from "../../types/ScanParameterInfo";
import { ParameterDisplayGroupsContext } from "../../contexts/ParameterDisplayGroupsContext";
import { DeviceInfoContext } from "../../contexts/DeviceInfoContext";

const generateScanValues = (
  start: number,
  stop: number,
  points: number,
  scatter: boolean,
) => {
  const values = Array.from(
    { length: points },
    (_, i) => start + (i * (stop - start)) / (points - 1),
  );
  return scatter ? values.sort(() => Math.random() - 0.5) : values;
};

export const ParameterCard = ({
  param,
  index,
}: {
  param: ScanParameterInfo;
  index: number;
}) => {
  const { state, dispatch } = useScanContext();

  const [parameterDisplayGroups, parameterNamespaceToDisplayGroup] = useContext(
    ParameterDisplayGroupsContext,
  );
  const deviceInfo = useContext(DeviceInfoContext);
  const parameterSources: Record<string, string[]> = {
    ...parameterNamespaceToDisplayGroup,
    Devices: Object.keys(deviceInfo),
  };
  console.log(parameterSources);

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
          return [shortId, shortId];
        }),
      );
    }

    const key = `${param.namespace} (${groupKey})`;
    const group = parameterDisplayGroups[key] || {};
    return Object.fromEntries(
      Object.entries(group).map(([paramId, meta]) => [paramId, meta.display_name]),
    );
  }, [param, parameterDisplayGroups, deviceInfo]);

  return (
    <Box display="flex" flexDirection="column" gap={1}>
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <FormControl fullWidth size="small">
          <InputLabel>Namespace</InputLabel>
          <Select
            title={param.namespace}
            value={param.namespace}
            onChange={(e) => {
              dispatch({
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
        <IconButton onClick={() => dispatch({ type: "REMOVE_PARAMETER", index })}>
          <DeleteIcon />
        </IconButton>
      </Box>
      <FormControl fullWidth size="small" disabled={!param.namespace}>
        <InputLabel>
          {param.namespace === "Devices" ? "Device Name" : "Display Group"}
        </InputLabel>
        <Select
          value={param.deviceNameOrDisplayGroup}
          onChange={(e) => {
            dispatch({
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
          value={param.id}
          title={param.id}
          onChange={(e) => {
            dispatch({
              type: "UPDATE_PARAMETER",
              index,
              payload: { id: e.target.value },
            });
          }}
          renderValue={(value) => {
            const selectedDisplayName = parameterOptions[value];
            console.log(`${value} in `, parameterOptions);
            if (selectedDisplayName === undefined) return value;
            return selectedDisplayName.length > 30
              ? selectedDisplayName.slice(0, 30) + "..."
              : selectedDisplayName;
          }}
        >
          {Object.entries(parameterOptions).map(([paramId, displayName]) => (
            <MenuItem key={paramId} value={paramId} title={paramId}>
              {displayName}
            </MenuItem>
          ))}
        </Select>
      </FormControl>
      <Box display="flex" flexDirection="column" gap={1}>
        <TextField
          required
          label="Start"
          size="small"
          type="number"
          fullWidth
          value={param.generation.start}
          onChange={(e) =>
            dispatch({
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
                  param.generation.scatter,
                ),
              },
            })
          }
          variant="outlined"
        />
        <TextField
          required
          label="Stop"
          size="small"
          type="number"
          fullWidth
          value={param.generation.stop}
          onChange={(e) =>
            dispatch({
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
                  param.generation.scatter,
                ),
              },
            })
          }
          variant="outlined"
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
            dispatch({
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
                  param.generation.scatter,
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
      </Box>
      <FormControlLabel
        control={
          <Checkbox
            checked={state.parameters[index!]?.generation.scatter ?? false}
            onChange={(e) => {
              dispatch({
                type: "UPDATE_PARAMETER",
                index: index!,
                payload: {
                  generation: {
                    ...state.parameters[index!]?.generation,
                    scatter: e.target.checked,
                  },
                },
              });
            }}
          />
        }
        label="Scatter"
      />
    </Box>
  );
};
