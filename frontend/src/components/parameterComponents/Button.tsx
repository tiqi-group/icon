import React, { useContext, useState } from "react";
import { Box, Button, Typography } from "@mui/material";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { useScanContext } from "../../contexts/ScanContext";
import { HelpButton } from "../HelpButtonComponent";
import { updateParameterValue } from "../../utils/updateParameterValue";

interface ButtonComponentProps {
  id: string;
  label?: string;
}

export const ButtonComponent = React.memo(({ id, label }: ButtonComponentProps) => {
  const { handleRightClick } = useScanContext();
  const parameterMetadata = useContext(ParameterMetadataContext);

  const displayName = label ?? parameterMetadata[id]?.display_name ?? id;
  const [value, setValue] = useState<boolean>(
    Boolean(parameterMetadata[id]?.default_value ?? false),
  );
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
        color={value === true ? "success" : "inherit"}
        onClick={() => onClick(!value)}
        onContextMenu={(e) => handleRightClick(e, id)}
      >
        {value === true ? "On" : "Off"}
      </Button>
    </Box>
  );
});
