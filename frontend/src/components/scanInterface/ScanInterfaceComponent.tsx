import React, { useState } from "react";
import {
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  TextField,
  Button,
  FormHelperText,
} from "@mui/material";
import { useScanContext } from "../../hooks/useScanContext";
import { submitJob } from "../../utils/submitJob";
import ScanParameterTable from "./ScanParameterTable";

interface ScanInterfaceProps {
  experimentId: string;
}
const ScanInterface = ({ experimentId }: ScanInterfaceProps) => {
  const { state: scanInfoState, dispatch: scanInfoDispatch } = useScanContext();
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
    if (scanInfoState.priority < 1 || scanInfoState.priority > 20) {
      newErrors.priority = "Priority must be between 1 and 20";
      valid = false;
    }

    // Validate number of shots
    if (scanInfoState.shots < 1) {
      newErrors.shots = "Number of shots must be at least 1";
      valid = false;
    }

    // Validate scan repetitions
    if (scanInfoState.repetitions < 1) {
      newErrors.repetitions = "Scan repetitions must be at least 1";
      valid = false;
    }

    // Validate scan parameters
    for (const param of scanInfoState.parameters) {
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
      if (param.generation.stop - param.generation.start == 0) {
        newErrors.parameters = "Start and stop cannot be the same";
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
      submitJob(experimentId, scanInfoState);
    }
  };

  return (
    <div style={{ display: "flex", gap: 16, paddingBottom: 16 }}>
      <ScanParameterTable />

      <div style={{ display: "flex", gap: 8, flexDirection: "column", paddingTop: 40 }}>
        <FormControl>
          <InputLabel>Priority</InputLabel>
          <Select
            label="Priority"
            size="small"
            value={scanInfoState.priority}
            onChange={(e) =>
              scanInfoDispatch({
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
          value={scanInfoState.shots}
          onChange={(e) =>
            scanInfoDispatch({ type: "SET_SHOTS", payload: Number(e.target.value) })
          }
          error={scanInfoState.shots < 1}
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
          value={scanInfoState.repetitions}
          onChange={(e) =>
            scanInfoDispatch({
              type: "SET_REPETITIONS",
              payload: Number(e.target.value),
            })
          }
          error={scanInfoState.repetitions < 1}
          slotProps={{
            input: {
              inputProps: {
                min: 1,
              },
            },
          }}
        />

        {errors.parameters && (
          <div style={{ color: "var(--mui-palette-error-main)", fontSize: "0.875rem" }}>
            {errors.parameters}
          </div>
        )}

        <Button
          type="submit"
          variant="contained"
          color="primary"
          onClick={handleSubmit}
        >
          Run
        </Button>
      </div>
    </div>
  );
};

export default ScanInterface;
