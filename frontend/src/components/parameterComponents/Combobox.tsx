import { useParameter } from "../../hooks/useParameter";
import { updateParameterValue } from "../../utils/updateParameterValue";
import {
  FormControl,
  MenuItem,
  Select,
  SelectChangeEvent,
  Typography,
} from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";
import React, { useCallback } from "react";

interface ComboboxProps {
  id: string;
  defaultValue: string;
  displayName: string;
  value?: string;
  allowedValues: string[];
}

export const Combobox = React.memo(
  ({
    id,
    defaultValue,
    displayName,
    allowedValues,
    value: localValue,
  }: ComboboxProps) => {
    const [value, setValue] = useParameter(id);
    const displayValue = localValue ?? value ?? defaultValue;

    const handleChange = useCallback(
      (event: SelectChangeEvent<string | number | boolean>) => {
        const newValue = event.target.value;
        updateParameterValue(id, newValue);
        setValue(newValue);
      },
      [id, setValue],
    );

    const isUpToDate = localValue == null || value == null || localValue == value;
    const style = isUpToDate ? {} : { backgroundColor: "#f851497e" };
    const title = isUpToDate ? undefined : `Value: ${value}`;

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Typography noWrap>{displayName ?? id}</Typography>
          {id && <HelpButton docString={id} />}
        </div>
        <FormControl size="small">
          <Select value={displayValue} onChange={handleChange} sx={style} title={title}>
            {allowedValues.map((value) => (
              <MenuItem key={value} value={value}>
                {value}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </div>
    );
  },
);
