import { useState } from "react";
import { BaseNumberComponent } from "../parameterComponents/BaseNumberComponent";
import { BaseTextComponent } from "../settings/BaseTextComponent";
import { updateConfiguration } from "../../utils/updateConfiguration";

interface EditableSettingFieldProps {
  configKey: string;
  label: string;
  value: string | number;
  onAfterUpdate?: () => void;
}

export const EditableSettingField = ({
  configKey,
  label,
  value,
  onAfterUpdate,
}: EditableSettingFieldProps) => {
  const [inputValue, setInputValue] = useState(String(value));

  const handleUpdate = (val: string) => {
    const parsed = typeof value === "number" ? Number(val) : val;
    updateConfiguration(configKey, parsed);
    if (onAfterUpdate) onAfterUpdate();
  };

  const commonProps = {
    id: configKey,
    displayName: label,
    value: inputValue,
    onChange: setInputValue,
    onBlur: handleUpdate,
  };

  return typeof value === "number" ? (
    <BaseNumberComponent {...commonProps} />
  ) : (
    <BaseTextComponent {...commonProps} />
  );
};
