import React, { useContext } from "react";
import { Button, Typography } from "@mui/material";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { HelpButton } from "../HelpButtonComponent";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { useParameter } from "../../hooks/useParameter";

interface ButtonComponentProps {
  id: string;
  namespace: string;
  displayGroup: string;
  scanIndex: number | null;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    namespace: string,
    displayGroup: string,
  ) => void;
}

export const ButtonComponent = React.memo(
  ({ id, namespace, displayGroup, scanIndex, onContextMenu }: ButtonComponentProps) => {
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
      <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <Typography noWrap>{displayName}</Typography>
          {id && <HelpButton docString={id} />}
        </div>

        <Button
          variant="outlined"
          color={displayValue === true ? "success" : "inherit"}
          onClick={() => onClick(!displayValue)}
          onContextMenu={(e) => onContextMenu?.(e, id, displayGroup, namespace)}
          sx={{ backgroundColor: scanIndex !== null ? "#186fc67e" : undefined }}
          title={scanIndex !== null ? `Scan parameter ${scanIndex + 1}` : undefined}
        >
          {displayValue === true ? "On" : "Off"}
        </Button>
      </div>
    );
  },
);
