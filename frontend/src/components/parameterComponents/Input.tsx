import React, { useRef } from "react";
import { Typography } from "@mui/material";
import { Field } from "@base-ui-components/react";
import "./Number.css";
import { HelpButton } from "../HelpButtonComponent";
import { numberValid } from "../../utils/numberValid";

interface InputProps {
  id: string;
  label?: string;
  value: string;
  type: "number" | "string";
  unit?: string;
  min?: number;
  max?: number;
  error?: boolean;
  onChange: (newValue: string) => void;
  onBlur: (value: string) => void;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
  ) => void;
  description?: string;
  inputBackgroundColor?: string;
  title?: string;
}
export const Input = React.memo(
  ({
    id,
    label,
    value,
    type,
    unit,
    min = Number.NEGATIVE_INFINITY,
    max = Number.POSITIVE_INFINITY,
    error = false,
    onChange,
    onBlur,
    onContextMenu,
    description,
    inputBackgroundColor,
    title,
  }: InputProps) => {
    const adornmentRef = useRef<HTMLSpanElement | null>(null);

    const validate = () => {
      if (type == "number")
        return numberValid(value, min, max) ? null : `Invalid input ${value}`;
      return null;
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) =>
      onChange(e.target.value);

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        onBlur(value);
      } else if ((e.key === "ArrowUp" || e.key === "ArrowDown") && type == "number") {
        e.preventDefault();
        const newVal = String(
          Number.parseFloat(value) + (e.key === "ArrowUp" ? 1 : -1),
        );
        if (numberValid(newVal, min, max)) onChange(newVal);
      }
    };

    return (
      <div style={{ display: "flex", alignItems: "center", padding: "4px 0" }}>
        {label && (
          <div style={{ display: "flex", alignItems: "center", padding: "0 4px 0 0" }}>
            <Typography noWrap>{label}</Typography>
            {description && <HelpButton docString={description} />}
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
              min={min}
              max={max}
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
