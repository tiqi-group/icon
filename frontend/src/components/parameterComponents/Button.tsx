import React, { useContext } from "react";
import { Box, Button, Typography } from "@mui/material";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { useScanContext } from "../../contexts/ScanContext";
import { HelpButton } from "../HelpButtonComponent";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { useParameter } from "../../hooks/useParameter";

interface ButtonComponentProps {
  id: string;
  label?: string;
}

export const ButtonComponent = React.memo(({ id, label }: ButtonComponentProps) => {
  const { handleRightClick } = useScanContext();
  const parameterMetadata = useContext(ParameterMetadataContext);

  const displayName = label ?? parameterMetadata[id]?.display_name ?? id;
  const [value, setValue] = useParameter(id);
  const displayValue = Boolean(value ?? parameterMetadata[id]?.default_value ?? false);
  const onClick = (newValue: boolean) => {
    updateParameterValue(id, newValue);
    setValue(newValue);
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      <Box display="flex" alignItems="center" gap={1}>
        <Typography noWrap>{displayName}</Typography>
        {id && <HelpButton docString={id} />}
      </Box>

      <Button
        variant="outlined"
        color={displayValue === true ? "success" : "inherit"}
        onClick={() => onClick(!displayValue)}
        onContextMenu={(e) => handleRightClick(e, id)}
      >
        {displayValue === true ? "On" : "Off"}
      </Button>
    </Box>
  );
});
