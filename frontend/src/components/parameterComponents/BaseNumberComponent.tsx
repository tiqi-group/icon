import React, { useRef } from "react";
import { Typography } from "@mui/material";
import { Field } from "@base-ui-components/react";
import "./Number.css";
import { HelpButton } from "../HelpButtonComponent";
import { numberValid } from "../../utils/numberValid";

interface BaseNumberComponentProps {
  id: string;
  displayName?: string;
  value: string;
  unit?: string;
  minValue?: number;
  maxValue?: number;
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
export const BaseNumberComponent = React.memo(
  ({
    id,
    displayName,
    value,
    unit,
    minValue = Number.NEGATIVE_INFINITY,
    maxValue = Number.POSITIVE_INFINITY,
    error = false,
    onChange,
    onBlur,
    onContextMenu,
    docString,
    inputBackgroundColor,
    title,
  }: BaseNumberComponentProps) => {
    const adornmentRef = useRef<HTMLSpanElement | null>(null);

    const validate = () =>
      numberValid(value, minValue, maxValue) ? null : `Invalid input ${value}`;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange(e.target.value);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        onBlur(value);
      } else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        e.preventDefault();
        const newVal = String(
          Number.parseFloat(value) + (e.key === "ArrowUp" ? 1 : -1),
        );
        if (numberValid(newVal, minValue, maxValue)) onChange(newVal);
      }
    };

    return (
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        {displayName && (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Typography noWrap>{displayName}</Typography>
            {docString && <HelpButton docString={docString} />}
          </div>
        )}
        <Field.Root className="Field" invalid={error} validate={validate}>
          <div className="InputWrapper">
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
            {unit && (
              <span ref={adornmentRef} className="EndAdornment">
                {unit}
              </span>
            )}
          </div>
        </Field.Root>
      </div>
    );
  },
);
