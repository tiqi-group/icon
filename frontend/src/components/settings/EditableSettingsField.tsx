import { useState } from "react";
import { updateConfiguration } from "../../utils/updateConfiguration";
import { Input } from "../parameterComponents/Input";

interface EditableSettingFieldProps {
  configKey: string;
  label: string;
  value: string | number | null;
  description?: string;
  onAfterUpdate?: () => void;
  onUpdate?: (val: string | number | null) => void;
}

export const EditableSettingField = ({
  configKey,
  label,
  value,
  description,
  onAfterUpdate,
  onUpdate,
}: EditableSettingFieldProps) => {
  const [inputValue, setInputValue] = useState(value === null ? "" : String(value));
  const type = typeof value as "number" | "string";

  const handleUpdate = (val: string) => {
    let parsed: string | number | null;

    if (val === "") {
      parsed = null;
    } else if (typeof value === "number") {
      parsed = Number(val);
    } else {
      parsed = val;
    }

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
