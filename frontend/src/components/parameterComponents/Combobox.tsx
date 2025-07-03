import { useContext } from "react";
import { useParameter } from "../../hooks/useParameter";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import {
  Box,
  FormControl,
  MenuItem,
  Select,
  SelectChangeEvent,
  Typography,
} from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";

interface ComboboxProps {
  id: string;
}

export const Combobox = ({ id }: ComboboxProps) => {
  const parameterMetadata = useContext(ParameterMetadataContext);

  const displayName = parameterMetadata[id]?.display_name ?? id;
  const allowedValues = parameterMetadata[id].allowed_values!;
  const [value, setValue] = useParameter(id);
  const displayValue = value ?? parameterMetadata[id]?.default_value ?? "";
  const handleChange = (event: SelectChangeEvent<string | number | boolean>) => {
    const newValue = event.target.value;
    updateParameterValue(id, newValue);
    setValue(newValue);
  };
  return (
    <>
      <Box display="flex" alignItems="center" gap={1}>
        <Box display="flex" alignItems="center" gap={1}>
          <Typography noWrap>{displayName}</Typography>
          {id && <HelpButton docString={id} />}
        </Box>
        <FormControl size="small">
          <Select value={displayValue} onChange={handleChange}>
            {allowedValues.map((value) => {
              return (
                <MenuItem key={value} value={value}>
                  {value}
                </MenuItem>
              );
            })}
          </Select>
        </FormControl>
      </Box>
    </>
  );
};
