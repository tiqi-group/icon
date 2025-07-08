import { useState } from "react";
import { BaseNumberComponent } from "../parameterComponents/BaseNumberComponent";
import { BaseTextComponent } from "../settings/BaseTextComponent";
import { updateConfiguration } from "../../utils/updateConfiguration";

interface EditableSettingFieldProps {
  configKey: string;
  label: string;
  value: string | number;
  description?: string;
  onAfterUpdate?: () => void;
}

export const EditableSettingField = ({
  configKey,
  label,
  value,
  description,
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
    docString: description,
  };

  return typeof value === "number" ? (
    <BaseNumberComponent {...commonProps} />
  ) : (
    <BaseTextComponent {...commonProps} />
  );
};
