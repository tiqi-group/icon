import React from "react";
import { Box, Typography, Button } from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";
import { updateConfiguration } from "../../utils/updateConfiguration";

interface BaseButtonComponentProps {
  id: string;
  label: string;
  value: boolean;
  docString?: string;
}

export const BaseButtonComponent = React.memo(
  ({ id, label, value, docString }: BaseButtonComponentProps) => {
    const onClick = (val: boolean) => {
      updateConfiguration(id, val);
    };

    return (
      <Box display="flex" alignItems="center" gap={1}>
        <Box display="flex" alignItems="center" gap={1}>
          <Typography noWrap>{label}</Typography>
          {docString && <HelpButton docString={docString} />}
        </Box>
        <Button variant="contained" onClick={() => onClick(!value)}>
          {value === true ? "True" : "False"}
        </Button>
      </Box>
    );
  },
);
