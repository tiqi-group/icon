import React from "react";
import { Typography, Button } from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";
import { updateConfiguration } from "../../utils/updateConfiguration";

interface BaseButtonComponentProps {
  id: string;
  label: string;
  value: boolean;
  description?: string;
}

export const BaseButtonComponent = React.memo(
  ({ id, label, value, description }: BaseButtonComponentProps) => {
    const onClick = (val: boolean) => {
      updateConfiguration(id, val);
    };

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <Typography noWrap>{label}</Typography>
          {description && <HelpButton docString={description} />}
        </div>
        <Button variant="contained" onClick={() => onClick(!value)}>
          {value === true ? "True" : "False"}
        </Button>
      </div>
    );
  },
);
