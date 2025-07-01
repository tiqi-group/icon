import { useContext, useState } from "react";
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
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
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

  const parameterMetadata = useContext(ParameterMetadataContext);

  return (
    <Box display="flex" flexDirection="column" gap={1}>
      <Box display="flex" alignItems="center" justifyContent="space-between">
        <FormControl fullWidth size="small">
          <InputLabel>Parameter ID</InputLabel>
          <Select
            value={param.id}
            onChange={(e) =>
              dispatch({
                type: "UPDATE_PARAMETER",
                index,
                payload: { id: e.target.value },
              })
            }
            renderValue={(selected) => {
              const truncated =
                selected.length > 30 ? selected.slice(0, 30) + "..." : selected;
              return truncated;
            }}
          >
            {Object.keys(parameterMetadata).map((paramId) => (
              <MenuItem key={paramId} value={paramId}>
                {paramId}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        <IconButton onClick={() => dispatch({ type: "REMOVE_PARAMETER", index })}>
          <DeleteIcon />
        </IconButton>
      </Box>
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
