import React from "react";
import { Box, Typography } from "@mui/material";
import { Field } from "@base-ui-components/react";
import { HelpButton } from "../HelpButtonComponent";

interface BaseTextComponentProps {
  id: string;
  displayName?: string;
  value: string;
  error?: boolean;
  onChange: (newValue: string) => void;
  onBlur: (value: string) => void;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
  ) => void;
  docString?: string;
  inputBackgroundColor?: string;
  title?: string;
}

export const BaseTextComponent = React.memo(
  ({
    id,
    displayName,
    value,
    error = false,
    onChange,
    onBlur,
    onContextMenu,
    docString,
    inputBackgroundColor,
    title,
  }: BaseTextComponentProps) => {
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange(e.target.value);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        onBlur(value);
      }
    };

    return (
      <Box display="flex" alignItems="center" gap={1}>
        {displayName && (
          <Box display="flex" alignItems="center" gap={1}>
            <Typography noWrap>{displayName}</Typography>
            {docString && <HelpButton docString={docString} />}
          </Box>
        )}
        <Field.Root className="Field" invalid={error}>
          <Box className="InputWrapper">
            <Field.Control
              title={error ? undefined : title}
              style={{
                backgroundColor: inputBackgroundColor,
              }}
              className="Input"
              value={value}
              onChange={handleChange}
              onBlur={() => onBlur(value)}
              onKeyDown={handleKeyDown}
              onContextMenu={(e) => onContextMenu?.(e, id)}
            />
          </Box>
        </Field.Root>
      </Box>
    );
  },
);
