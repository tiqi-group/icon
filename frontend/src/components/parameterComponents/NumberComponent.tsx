import React, { useEffect, useState } from "react";
import { TextField, InputAdornment, Box, Tooltip, Typography } from "@mui/material";
import HelpOutlineIcon from "@mui/icons-material/HelpOutline";
import { SerializedObject } from "../../types/SerializedObject";
import { QuantityMap } from "../../types/QuantityMap";

export interface QuantityObject {
  type: "Quantity";
  readonly: boolean;
  value: QuantityMap;
  doc: string | null;
}
export interface IntObject {
  type: "int";
  readonly: boolean;
  value: number;
  doc: string | null;
}
export interface FloatObject {
  type: "float";
  readonly: boolean;
  value: number;
  doc: string | null;
}
export type NumberObject = IntObject | FloatObject | QuantityObject;

interface NumberComponentProps {
  type: "float" | "int" | "Quantity";
  fullAccessPath: string;
  value: number;
  readOnly: boolean;
  docString: string | null;
  unit?: string;
  // addNotification: (message: string, levelname?: string) => void;
  // changeCallback?: (value: SerializedObject, callback?: (ack: unknown) => void) => void;
  onContextMenu?: (event: React.MouseEvent<HTMLDivElement>, paramId: string) => void;
  displayName?: string;
  id: string;
}

const handleArrowKey = (
  key: string,
  value: string,
  selectionStart: number,
  // selectionEnd: number
) => {
  // Split the input value into the integer part and decimal part
  const parts = value.split(".");
  const beforeDecimalCount = parts[0].length; // Count digits before the decimal
  const afterDecimalCount = parts[1] ? parts[1].length : 0; // Count digits after the decimal

  const isCursorAfterDecimal = selectionStart > beforeDecimalCount;

  // Calculate the increment/decrement value based on the cursor position
  let increment = 0;
  if (isCursorAfterDecimal) {
    increment = Math.pow(10, beforeDecimalCount + 1 - selectionStart);
  } else {
    increment = Math.pow(10, beforeDecimalCount - selectionStart);
  }

  // Convert the input value to a number, increment or decrement it based on the
  // arrow key
  const numValue = parseFloat(value) + (key === "ArrowUp" ? increment : -increment);

  // Convert the resulting number to a string, maintaining the same number of digits
  // after the decimal
  const newValue = numValue.toFixed(afterDecimalCount);

  // Check if the length of the integer part of the number string has in-/decreased
  const newBeforeDecimalCount = newValue.split(".")[0].length;
  if (newBeforeDecimalCount > beforeDecimalCount) {
    // Move the cursor one position to the right
    selectionStart += 1;
  } else if (newBeforeDecimalCount < beforeDecimalCount) {
    // Move the cursor one position to the left
    selectionStart -= 1;
  }
  return { value: newValue, selectionStart };
};

const handleBackspaceKey = (
  value: string,
  selectionStart: number,
  selectionEnd: number,
) => {
  if (selectionEnd > selectionStart) {
    // If there is a selection, delete all characters in the selection
    return {
      value: value.slice(0, selectionStart) + value.slice(selectionEnd),
      selectionStart,
    };
  } else if (selectionStart > 0) {
    return {
      value: value.slice(0, selectionStart - 1) + value.slice(selectionStart),
      selectionStart: selectionStart - 1,
    };
  }
  return { value, selectionStart };
};

const handleDeleteKey = (
  value: string,
  selectionStart: number,
  selectionEnd: number,
) => {
  if (selectionEnd > selectionStart) {
    // If there is a selection, delete all characters in the selection
    return {
      value: value.slice(0, selectionStart) + value.slice(selectionEnd),
      selectionStart,
    };
  } else if (selectionStart < value.length) {
    return {
      value: value.slice(0, selectionStart) + value.slice(selectionStart + 1),
      selectionStart,
    };
  }
  return { value, selectionStart };
};

const handleNumericKey = (
  key: string,
  value: string,
  selectionStart: number,
  selectionEnd: number,
) => {
  let newValue = value;

  // Check if a number key or a decimal point key is pressed
  if (key === "." && value.includes(".")) {
    // Check if value already contains a decimal. If so, ignore input.
    console.warn("Invalid input! Ignoring...");
    return { value, selectionStart };
  }

  // Handle minus sign input
  if (key === "-") {
    if (selectionStart === 0 && selectionEnd > selectionStart) {
      // Replace selection with minus if selection starts at 0
      newValue = "-" + value.slice(selectionEnd);
      selectionStart = 1;
    } else if (selectionStart === 0 && !value.startsWith("-")) {
      // Add minus at the beginning if it doesn't exist
      newValue = "-" + value;
      selectionStart = 1;
    } else if (
      (selectionStart === 0 || selectionStart === 1) &&
      value.startsWith("-")
    ) {
      // Remove minus if it exists
      newValue = value.slice(1);
      selectionStart = 0;
    }

    return { value: newValue, selectionStart };
  }

  // Add the new key at the cursor's position
  if (selectionEnd > selectionStart) {
    // If there is a selection, replace it with the key
    newValue = value.slice(0, selectionStart) + key + value.slice(selectionEnd);
  } else {
    // Otherwise, insert the key at the cursor position
    newValue = value.slice(0, selectionStart) + key + value.slice(selectionStart);
  }

  return { value: newValue, selectionStart: selectionStart + 1 };
};

export const NumberComponent = (props: NumberComponentProps) => {
  const {
    fullAccessPath,
    value,
    readOnly,
    type,
    docString,
    unit,
    // addNotification,
    // changeCallback = () => {},
    onContextMenu = () => {},
    displayName,
    id,
  } = props;

  const [cursorPosition, setCursorPosition] = useState<number | null>(null);
  const [inputString, setInputString] = useState(value.toString());

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    const { key, target } = event;

    const inputTarget = target as HTMLInputElement;
    if (key === "F1" || key === "F5" || key === "F12" || key === "Tab") {
      return;
    }
    event.preventDefault();

    // Get the current input value and cursor position
    const { value } = inputTarget;
    const selectionEnd = inputTarget.selectionEnd ?? 0;
    let selectionStart = inputTarget.selectionStart ?? 0;

    let newValue: string = value;
    if (event.ctrlKey && key === "a") {
      // Select everything when pressing Ctrl + a
      inputTarget.setSelectionRange(0, value.length);
      return;
    } else if (key === "ArrowRight" || key === "ArrowLeft") {
      // Move the cursor with the arrow keys and store its position
      selectionStart = key === "ArrowRight" ? selectionStart + 1 : selectionStart - 1;
      setCursorPosition(selectionStart);
      return;
    } else if ((key >= "0" && key <= "9") || key === "-") {
      // Check if a number key or a decimal point key is pressed
      ({ value: newValue, selectionStart } = handleNumericKey(
        key,
        value,
        selectionStart,
        selectionEnd,
      ));
    } else if (key === "." && (type === "float" || type === "Quantity")) {
      ({ value: newValue, selectionStart } = handleNumericKey(
        key,
        value,
        selectionStart,
        selectionEnd,
      ));
    } else if (key === "ArrowUp" || key === "ArrowDown") {
      ({ value: newValue, selectionStart } = handleArrowKey(
        key,
        value,
        selectionStart,
        // selectionEnd
      ));
    } else if (key === "Backspace") {
      ({ value: newValue, selectionStart } = handleBackspaceKey(
        value,
        selectionStart,
        selectionEnd,
      ));
    } else if (key === "Delete") {
      ({ value: newValue, selectionStart } = handleDeleteKey(
        value,
        selectionStart,
        selectionEnd,
      ));
    } else if (key === "Enter") {
      let serializedObject: SerializedObject;
      if (type === "Quantity") {
        serializedObject = {
          type: "Quantity",
          value: {
            magnitude: Number(newValue),
            unit: unit,
          } as QuantityMap,
          full_access_path: fullAccessPath,
          readonly: readOnly,
          doc: docString,
        };
      } else {
        serializedObject = {
          type: type,
          value: Number(newValue),
          full_access_path: fullAccessPath,
          readonly: readOnly,
          doc: docString,
        };
      }

      // changeCallback(serializedObject);
      return;
    } else {
      console.debug(key);
      return;
    }

    setInputString(newValue);

    // Save the current cursor position before the component re-renders
    setCursorPosition(selectionStart);
  };

  const emitValueChange = (newValue: string) => {
    let serializedObject: SerializedObject;
    if (type === "Quantity") {
      serializedObject = {
        type: "Quantity",
        value: { magnitude: Number(newValue), unit: unit } as QuantityMap,
        full_access_path: fullAccessPath,
        readonly: readOnly,
        doc: docString,
      };
    } else {
      serializedObject = {
        type: type,
        value: Number(newValue),
        full_access_path: fullAccessPath,
        readonly: readOnly,
        doc: docString,
      };
    }
    // changeCallback(serializedObject);
  };

  const handleBlur = () => {
    emitValueChange(inputString);
  };

  useEffect(() => {
    const numericInputString =
      type === "int" ? parseInt(inputString) : parseFloat(inputString);
    if (value !== numericInputString) {
      setInputString(value.toString());
    }

    let notificationMsg = `${fullAccessPath} changed to ${value}`;
    if (unit) {
      notificationMsg += ` ${unit}.`;
    }
    // addNotification(notificationMsg);
    console.log("Changed value");
  }, [value]);

  useEffect(() => {
    const inputElement = document.getElementById(id) as HTMLInputElement;
    if (inputElement && cursorPosition !== null) {
      inputElement.setSelectionRange(cursorPosition, cursorPosition);
    }
  });

  return (
    <Box display="flex" alignItems="center" gap={1}>
      {displayName && (
        <Box display="flex" alignItems="center" gap={1}>
          <Typography noWrap>{displayName}</Typography>
          {docString && (
            <Tooltip title={id} arrow>
              <HelpOutlineIcon fontSize="small" />
            </Tooltip>
          )}
        </Box>
      )}
      <TextField
        id={id}
        size="small"
        type="number"
        value={inputString}
        disabled={readOnly}
        fullWidth
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        onContextMenu={(event) => onContextMenu(event, id)}
        slotProps={{
          input: {
            endAdornment: unit ? (
              <InputAdornment position="end">{unit}</InputAdornment>
            ) : null,
          },
        }}
      />
    </Box>
  );
};

NumberComponent.displayName = "NumberComponent";
