import React from "react";
import { Typography, Button, ButtonProps } from "@mui/material";
import { HelpButton } from "../HelpButtonComponent";

interface BaseButtonProps {
  label: string;
  description?: string;
  onClick: () => void;
  color?: ButtonProps["color"];
  children: React.ReactNode;
  onContextMenu?: React.MouseEventHandler<HTMLButtonElement> | undefined;
  title?: string;
  backgroundColor?: string;
}

export const BaseButton = React.memo(
  ({
    label,
    description,
    onClick,
    color = "inherit",
    children,
    onContextMenu,
    title,
    backgroundColor,
  }: BaseButtonProps) => {
    return (
      <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
        <div style={{ display: "flex", alignItems: "center" }}>
          <Typography noWrap>{label}</Typography>
          {description && <HelpButton docString={description} />}
        </div>
        <Button
          variant="outlined"
          onClick={onClick}
          color={color}
          onContextMenu={onContextMenu}
          title={title}
          sx={{ backgroundColor: backgroundColor }}
        >
          {children}
        </Button>
      </div>
    );
  },
);
