import React, { useContext, useState } from "react";
import { useParameter } from "../../hooks/useParameter";
import { ParameterMetadataContext } from "../../contexts/ParameterMetadataContext";
import { useScanContext } from "../../hooks/useScanContext";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { BaseNumberComponent, numberValid } from "./BaseNumberComponent";

interface Props {
  id: string;
}

export const ParameterNumberComponent = React.memo(({ id }: Props) => {
  const { handleRightClick } = useScanContext();
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
    <BaseNumberComponent
      id={id}
      displayName={meta.display_name}
      unit={meta.unit}
      value={displayValue}
      minValue={minValue}
      maxValue={maxValue}
      error={error}
      onChange={handleChange}
      onBlur={handleBlur}
      onContextMenu={(event) => handleRightClick(event, id)}
      docString={id}
    />
  );
});
