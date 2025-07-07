import React, { useContext } from "react";
import { Box, Button, Typography } from "@mui/material";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { useScanContext } from "../../hooks/useScanContext";
import { HelpButton } from "../HelpButtonComponent";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { useParameter } from "../../hooks/useParameter";

interface ButtonComponentProps {
  id: string;
  namespace: string;
  displayGroup: string;
  scanIndex: number | null;
}

export const ButtonComponent = React.memo(
  ({ id, namespace, displayGroup, scanIndex }: ButtonComponentProps) => {
    const { handleRightClick } = useScanContext();
    const parameterMetadata = useContext(ParameterMetadataContext);

    const displayName = parameterMetadata[id]?.display_name ?? id;
    const [value, setValue] = useParameter(id);
    const displayValue = Boolean(
      value ?? parameterMetadata[id]?.default_value ?? false,
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
          color={displayValue === true ? "success" : "inherit"}
          onClick={() => onClick(!displayValue)}
          onContextMenu={(e) => handleRightClick(e, id, displayGroup, namespace)}
          sx={{ backgroundColor: scanIndex !== null ? "#186fc67e" : undefined }}
          title={scanIndex !== null ? `Scan parameter ${scanIndex + 1}` : undefined}
        >
          {displayValue === true ? "On" : "Off"}
        </Button>
      </Box>
    );
  },
);
