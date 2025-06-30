import React, { useState } from "react";
import {
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Box,
  Button,
  FormHelperText,
} from "@mui/material";
import ScanParameterTable from "./ScanParameterTable";
import { useScanContext } from "../hooks/useScanContext";
import { runMethod } from "../socket";

interface ScanInterfaceProps {
  experimentId: string;
}
const ScanInterface = ({ experimentId }: ScanInterfaceProps) => {
  const { state, dispatch } = useScanContext();
  const [errors, setErrors] = useState<{
    priority?: string;
    shots?: string;
    repetitions?: string;
    parameters?: string;
  }>({});

  const validateForm = () => {
    let valid = true;
    const newErrors: typeof errors = {};

    // Validate priority
    if (state.priority < 1 || state.priority > 20) {
      newErrors.priority = "Priority must be between 1 and 20";
      valid = false;
    }

    // Validate number of shots
    if (state.shots < 1) {
      newErrors.shots = "Number of shots must be at least 1";
      valid = false;
    }

    // Validate scan repetitions
    if (state.repetitions < 1) {
      newErrors.repetitions = "Scan repetitions must be at least 1";
      valid = false;
    }

    // Validate scan parameters
    for (const param of state.parameters) {
      if (!param.id) {
        newErrors.parameters = "Each scan parameter must have an ID";
        valid = false;
        break;
      }
      if (param.generation.points < 1) {
        newErrors.parameters = "Points must be at least 1";
        valid = false;
        break;
      }
    }

    setErrors(newErrors);
    return valid;
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();

    if (validateForm()) {
      console.log("Scan Config:", state);
      runMethod("scheduler.submit_job", [], {
        experiment_id: experimentId,
        scan_parameters: state.parameters,
      });
      alert("Scan submitted!");
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <Box display="flex" gap={2} pb={2}>
        <ScanParameterTable />

        <Box display="flex" gap={1} flexDirection="column" pt={5}>
          <FormControl>
            <InputLabel>Priority</InputLabel>
            <Select
              label="Priority"
              size="small"
              value={state.priority}
              onChange={(e) =>
                dispatch({
                  type: "SET_PRIORITY",
                  payload: Number(e.target.value),
                })
              }
            >
              {Array.from({ length: 20 }, (_, i) => i + 1).map((num) => (
                <MenuItem key={num} value={num}>
                  {num}
                </MenuItem>
              ))}
            </Select>
            {errors.priority && <FormHelperText>{errors.priority}</FormHelperText>}
          </FormControl>

          <TextField
            label="Number of Shots"
            type="number"
            size="small"
            value={state.shots}
            onChange={(e) =>
              dispatch({ type: "SET_SHOTS", payload: Number(e.target.value) })
            }
            error={state.shots < 1}
            helperText={errors.shots}
            slotProps={{
              input: {
                inputProps: {
                  min: 1,
                },
              },
            }}
          />

          <TextField
            label="Scan Repetitions"
            type="number"
            size="small"
            value={state.repetitions}
            onChange={(e) =>
              dispatch({ type: "SET_REPETITIONS", payload: Number(e.target.value) })
            }
            error={state.repetitions < 1}
            slotProps={{
              input: {
                inputProps: {
                  min: 1,
                },
              },
            }}
          />

          {errors.parameters && (
            <Box sx={{ color: "error.main", fontSize: "0.875rem" }}>
              {errors.parameters}
            </Box>
          )}

          <Button type="submit" variant="contained" color="primary">
            Run
          </Button>
        </Box>
      </Box>
    </form>
  );
};

export default ScanInterface;
