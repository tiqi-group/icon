import React from "react";
import { Tooltip, IconButton } from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";

interface DocStringProps {
  docString?: string | null;
}

export const HelpButton = (props: DocStringProps) => {
  const { docString } = props;

  if (!docString) {
    return null; // render nothing if docString is not provided
  }

  return (
    <Tooltip title={docString} placement="bottom" arrow>
      <IconButton>
        <HelpOutlineIcon fontSize="small" />
      </IconButton>
    </Tooltip>
  );
};

HelpButton.displayName = "HelpButton";
