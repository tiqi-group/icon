import { IconButton, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import DeleteIcon from "@mui/icons-material/Delete";
import PinIcon from "@mui/icons-material/Pin";
import AbcIcon from "@mui/icons-material/Abc";
import AddIcon from "@mui/icons-material/Add";
import { updateConfiguration } from "../../utils/updateConfiguration";
import { EditableSettingField } from "./EditableSettingsField";

interface EditableDictFieldProps {
  configKey: string;
  label: string;
  value: Record<string, string | number>;
}

export const EditableDictField = ({
  configKey,
  label,
  value,
}: EditableDictFieldProps) => {
  const [dict, setDict] = useState<Record<string, string | number>>({ ...value });
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  const handleUpdate = async (updated: Record<string, string | number>) => {
    setDict(updated);
    await updateConfiguration(configKey, updated);
  };

  const handleChange = async (key: string, val: string | number | null) => {
    const updated = { ...dict, [key]: val ?? "" };
    setDict(updated);
    await handleUpdate(updated);
  };

  const handleDelete = async (key: string) => {
    const updated = { ...dict };
    delete updated[key];
    await handleUpdate(updated);
  };

  const handleAdd = async () => {
    if (newKey.trim() === "") return;
    const updated = { ...dict, [newKey]: newValue };
    await handleUpdate(updated);
    setNewKey("");
    setNewValue("");
  };

  const toNumber = (value: string) => {
    const num = Number(value);
    return isNaN(num) ? 0 : num;
  };

  const handleToggleType = async (key: string) => {
    const value = dict[key];
    const newValue = typeof value === "string" ? toNumber(value) : value.toString();
    await handleChange(key, newValue);
  };

  return (
    <div>
      <Typography variant="subtitle2" gutterBottom>
        {label}
      </Typography>
      <Stack spacing={1}>
        {Object.entries(dict).map(([key, value]) => (
          <Stack key={key} direction="row" spacing={1} alignItems="center">
            <IconButton
              onClick={async () => await handleToggleType(key)}
              title={
                typeof value === "string"
                  ? "Click to change value type to a number"
                  : "Click to change value type to a string"
              }
              size="small"
            >
              {typeof value === "string" ? (
                <AbcIcon fontSize="small" />
              ) : (
                <PinIcon fontSize="small" />
              )}
            </IconButton>
            <EditableSettingField
              configKey={`${configKey}.${key}`}
              label={key}
              value={value}
              onUpdate={(value) => handleChange(key, value)}
            />
            <IconButton onClick={async () => handleDelete(key)} size="small">
              <DeleteIcon fontSize="small" />
            </IconButton>
          </Stack>
        ))}
        <Stack direction="row" spacing={1} alignItems="center" sx={{ mt: 1 }}>
          <TextField
            variant="outlined"
            size="small"
            label="New Key"
            value={newKey}
            onChange={(e) => setNewKey(e.target.value)}
            sx={{ minWidth: 160 }}
          />
          <TextField
            variant="outlined"
            size="small"
            label="New Value"
            value={newValue}
            onChange={(e) => setNewValue(e.target.value)}
            sx={{ minWidth: 160 }}
          />
          <IconButton onClick={handleAdd} size="small" sx={{ mt: "auto" }}>
            <AddIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Stack>
    </div>
  );
};
