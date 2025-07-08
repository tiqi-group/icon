import React, { useContext, useState } from "react";
import { useParameter } from "../../hooks/useParameter";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { numberValid } from "../../utils/numberValid";
import { Input } from "./Input";

interface Props {
  id: string;
  namespace: string;
  displayGroup: string;
  scanIndex: number | null;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    namespace: string,
    displayGroup: string,
  ) => void;
}

export const ParameterNumberComponent = React.memo(
  ({ id, namespace, displayGroup, scanIndex, onContextMenu }: Props) => {
    const parameterMetadata = useContext(ParameterMetadataContext);
    const [value, setValue] = useParameter(id);
    const [error, setError] = useState(false);

    const displayValue = String(value ?? parameterMetadata[id]?.default_value ?? "0");
    const minValue = parameterMetadata[id]?.min_value ?? Number.NEGATIVE_INFINITY;
    const maxValue = parameterMetadata[id]?.max_value ?? Number.POSITIVE_INFINITY;

    const handleChange = (val: string) => setValue(val);

    const handleBlur = (newValue: string) => {
      const parsedValue = Number.parseFloat(newValue);

      if (numberValid(newValue, minValue, maxValue)) {
        updateParameterValue(id, parsedValue);
        setError(false);
      } else {
        setError(true);
      }
    };

    const meta = parameterMetadata[id] ?? {};

    return (
      <Input
        id={id}
        label={meta.display_name}
        type="number"
        unit={meta.unit}
        value={displayValue}
        min={minValue}
        max={maxValue}
        error={error}
        onChange={handleChange}
        onBlur={handleBlur}
        onContextMenu={(event) => onContextMenu?.(event, id, displayGroup, namespace)}
        description={id}
        inputBackgroundColor={scanIndex !== null ? "#186fc67e" : undefined}
        title={scanIndex !== null ? `Scan parameter ${scanIndex + 1}` : undefined}
      />
    );
  },
);
