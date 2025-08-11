import { useState } from "react";
import { updateConfiguration } from "../../utils/updateConfiguration";
import { Input } from "../parameterComponents/Input";
import { useNotifications } from "@toolpad/core";

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
  const notifications = useNotifications();
  const [inputValue, setInputValue] = useState(value === null ? "" : String(value));
  const type = typeof value as "number" | "string";

  const handleUpdate = async (val: string) => {
    let parsed: string | number | null;

    if (val === "") {
      parsed = null;
    } else if (typeof value === "number") {
      parsed = Number(val);
    } else {
      parsed = val;
    }

    let err: Error | null = null;
    if (onUpdate) {
      onUpdate(parsed);
    } else {
      err = await updateConfiguration(configKey, parsed);
    }
    onAfterUpdate?.();

    if (err instanceof Error) {
      setInputValue(String(value));

      const msg = err.message || String(err);
      notifications.show(`Failed to update configuration: ${msg}`, {
        severity: "error",
      });
    }
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
