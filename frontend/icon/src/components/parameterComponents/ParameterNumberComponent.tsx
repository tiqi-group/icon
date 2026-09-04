import React, { useCallback, useState } from "react";
import { useParameter } from "../../hooks/useParameter";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { numberValid } from "../../utils/numberValid";
import { Input } from "./Input";

interface Props {
  id: string;
  namespace: string;
  displayGroup: string;
  scanIndex: number | null;
  value?: string;
  defaultValue: string;
  displayName: string;
  min?: number | null;
  max?: number | null;
  unit?: string;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    namespace: string,
    displayGroup: string,
  ) => void;
}

export const ParameterNumberComponent = React.memo(
  ({
    id,
    namespace,
    displayGroup,
    scanIndex,
    defaultValue,
    displayName,
    min,
    max,
    unit,
    onContextMenu,
    value: localValue,
  }: Props) => {
    const [value, setValue] = useParameter(id);
    const [error, setError] = useState(false);

    const displayValue = localValue ?? String(value ?? defaultValue);
    const minValue = min ?? Number.NEGATIVE_INFINITY;
    const maxValue = max ?? Number.POSITIVE_INFINITY;
    const isUpToDate = localValue == null || value == null || localValue == value;

    const handleChange = (val: string) => setValue(val);

    const handleBlur = useCallback(
      (newValue: string) => {
        const parsedValue = Number.parseFloat(newValue);

        if (numberValid(newValue, minValue, maxValue)) {
          updateParameterValue(id, parsedValue);
          setError(false);
        } else {
          setError(true);
        }
      },
      [setError, id],
    );
    const backgroundColor =
      scanIndex !== null ? "#186fc67e" : !isUpToDate ? "#f851497e" : undefined;
    const title =
      scanIndex !== null
        ? `Scan parameter ${scanIndex + 1}`
        : !isUpToDate
          ? `Value: ${value}`
          : undefined;

    return (
      <Input
        id={id}
        label={displayName}
        type="number"
        unit={unit}
        value={displayValue}
        min={minValue}
        max={maxValue}
        error={error}
        onChange={handleChange}
        onBlur={handleBlur}
        onContextMenu={(event) => onContextMenu?.(event, id, displayGroup, namespace)}
        description={id}
        inputBackgroundColor={backgroundColor}
        title={title}
      />
    );
  },
);
