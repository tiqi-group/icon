import { useState } from "react";
import { updateConfiguration } from "../../utils/updateConfiguration";
import { Input } from "../parameterComponents/Input";

interface EditableSettingFieldProps {
  configKey: string;
  label: string;
  value: string | number;
  description?: string;
  onAfterUpdate?: () => void;
  onUpdate?: (val: string | number) => void;
}

export const EditableSettingField = ({
  configKey,
  label,
  value,
  description,
  onAfterUpdate,
  onUpdate,
}: EditableSettingFieldProps) => {
  const [inputValue, setInputValue] = useState(String(value));
  const type = typeof value as "number" | "string";

  const handleUpdate = (val: string) => {
    const parsed = typeof value === "number" ? Number(val) : val;
    if (onUpdate) {
      onUpdate(parsed);
    } else {
      updateConfiguration(configKey, parsed);
    }
    onAfterUpdate?.();
  };

  const commonProps = {
    id: configKey,
    label,
    value: inputValue,
    onChange: setInputValue,
    onBlur: handleUpdate,
    description,
  };

  return <Input type={type} {...commonProps} />;
};
