import React, { useContext, useRef, useState } from "react";
import { Box, Typography } from "@mui/material";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { useScanContext } from "../../contexts/ScanContext";
import { Field } from "@base-ui-components/react";
import "./Number.css";
import { HelpButton } from "../HelpButtonComponent";

interface NumberComponentProps {
  id: string;
}

export const NumberComponent = (props: NumberComponentProps) => {
  const { handleRightClick } = useScanContext();

  const { id } = props;
  const parameterMetadata = useContext(ParameterMetadataContext);
  const [value, setValue] = useState<string>(
    String(parameterMetadata[id]?.default_value ?? ""),
  );
  const [error, setError] = useState(false);

  const minValue = parameterMetadata[id]?.min_value ?? Number.NEGATIVE_INFINITY;
  const maxValue = parameterMetadata[id]?.max_value ?? Number.POSITIVE_INFINITY;
  const adornmentRef = useRef<HTMLSpanElement | null>(null);

  const validate = () => {
    if (!numberValid(value)) {
      return `Invalid input ${value}`;
    }
    return null;
  };
  const validateAndLogValue = (newValue: string) => {
    if (!numberValid(newValue)) {
      console.error(`Invalid input ${newValue}`);
      setError(true);
    } else {
      console.log(`Final value: ${value}`);
      setError(false);
    }
  };

  const numberValid = (newValue: string) => {
    const parsedValue = Number.parseFloat(newValue);
    if (
      !isNaN(+newValue) &&
      !isNaN(parsedValue) &&
      parsedValue >= minValue &&
      parsedValue <= maxValue
    ) {
      return true;
    } else {
      return false;
    }
  };

  const handleChange = (
    event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    const newValue = event.target.value;
    setValue(newValue);

    if (numberValid(newValue)) {
      console.log(`Valid input: ${newValue}`);
    } else {
      console.warn("Invalid input or out of range");
    }
  };

  const handleBlur = () => {
    validateAndLogValue(value);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      handleBlur();
    } else if (event.key === "ArrowUp" || event.key === "ArrowDown") {
      event.preventDefault();
      const increment = 1;
      const newValue = String(
        parseFloat(value) + (event.key === "ArrowUp" ? increment : -increment),
      );
      if (numberValid(newValue)) {
        setValue(newValue);
      }
    }
  };

  return (
    <Box display="flex" alignItems="center" gap={1}>
      {parameterMetadata[id]?.display_name && (
        <Box display="flex" alignItems="center" gap={1}>
          <Typography noWrap>{parameterMetadata[id].display_name}</Typography>
          {id && <HelpButton docString={id} />}
        </Box>
      )}

      <Field.Root className="Field" invalid={error} validate={validate}>
        <Box className="InputWrapper">
          <Field.Control
            className="Input"
            // type="number"
            value={value}
            onChange={handleChange}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            onContextMenu={(event) => handleRightClick(event, id)}
            // style={{ paddingRight: `${adornmentWidth + 15}px` }}
          />
          {parameterMetadata[id]?.unit && (
            <span ref={adornmentRef} className="EndAdornment">
              {parameterMetadata[id].unit}
            </span>
          )}
        </Box>
      </Field.Root>
    </Box>
  );
};
