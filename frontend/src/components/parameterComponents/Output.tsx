import React from "react";
import { useParameter } from "../../hooks/useParameter";
import { HelpButton } from "../HelpButtonComponent";
import { Input, Typography, Button } from "@mui/material";

interface ButtonComponentProps<T> {
  id: string;
  label?: string;
  description?: string;
  scanIndex: number | null;
  defaultValue: T;
  value?: T | undefined;
}

export const Output = React.memo(
  ({
    id,
    scanIndex,
    defaultValue,
    label,
    description,
    value: localValue,
  }: ButtonComponentProps<string | boolean | number>) => {
    const [value, _setValue] = useParameter(id);
    const displayValue = localValue ?? value ?? defaultValue;
    const isUpToDate = localValue == null || value == null || localValue == value;
    const backgroundColor =
      scanIndex !== null ? "#186fc67e" : !isUpToDate ? "#f851497e" : undefined;
    const style = isUpToDate && scanIndex === null ? {} : { backgroundColor };

    const title =
      scanIndex !== null
        ? `Scan parameter ${scanIndex + 1}`
        : !isUpToDate
          ? `Value: ${value}`
          : undefined;

    return (
      <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
        {label && (
          <div style={{ display: "flex", alignItems: "center", padding: "0 4px 0 0" }}>
            <Typography noWrap>{label}</Typography>
            {description && <HelpButton docString={description} />}
          </div>
        )}
        {typeof defaultValue == "boolean" ? (
          <Button
            variant="outlined"
            color={displayValue === true ? "success" : "inherit"}
            title={title}
            sx={{ backgroundColor }}
          >
            {displayValue === true ? "On" : "Off"}
          </Button>
        ) : (
          <Input
            type="text"
            value={displayValue.toString()}
            readOnly={true}
            title={title}
            sx={style}
          />
        )}
      </div>
    );
  },
);
