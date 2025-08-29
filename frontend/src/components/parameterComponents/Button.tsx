import React, { useCallback } from "react";
import { updateParameterValue } from "../../utils/updateParameterValue";
import { useParameter } from "../../hooks/useParameter";
import { BaseButton } from "./BaseButton";

interface ButtonComponentProps {
  id: string;
  namespace: string;
  displayGroup: string;
  scanIndex: number | null;
  displayName: string;
  defaultValue: boolean;
  onContextMenu?: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    namespace: string,
    displayGroup: string,
  ) => void;
}

export const ButtonComponent = React.memo(
  ({
    id,
    namespace,
    displayGroup,
    scanIndex,
    displayName,
    defaultValue,
    onContextMenu,
  }: ButtonComponentProps) => {
    const [value, setValue] = useParameter(id);
    const displayValue = Boolean(value ?? defaultValue);
    const onClick = useCallback(
      (newValue: boolean) => {
        updateParameterValue(id, newValue);
        setValue(newValue);
      },
      [id, setValue],
    );

    return (
      <BaseButton
        label={displayName}
        color={displayValue === true ? "success" : "inherit"}
        onClick={() => onClick(!displayValue)}
        onContextMenu={(e) => onContextMenu?.(e, id, displayGroup, namespace)}
        backgroundColor={scanIndex !== null ? "#186fc67e" : undefined}
        description={id}
        title={scanIndex !== null ? `Scan parameter ${scanIndex + 1}` : undefined}
      >
        {displayValue === true ? "On" : "Off"}
      </BaseButton>
    );
  },
);
