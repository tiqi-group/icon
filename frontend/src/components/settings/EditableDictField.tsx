import { IconButton, Stack, TextField, Typography } from "@mui/material";
import { useState } from "react";
import DeleteIcon from "@mui/icons-material/Delete";
import AddIcon from "@mui/icons-material/Add";
import { updateConfiguration } from "../../utils/updateConfiguration";
import { EditableSettingField } from "./EditableSettingsField";

interface EditableDictFieldProps {
  configKey: string;
  label: string;
  value: Record<string, string>;
}

export const EditableDictField = ({
  configKey,
  label,
  value,
}: EditableDictFieldProps) => {
  const [dict, setDict] = useState<Record<string, string>>({ ...value });
  const [newKey, setNewKey] = useState("");
  const [newValue, setNewValue] = useState("");

  const handleUpdate = (updated: Record<string, string>) => {
    setDict(updated);
    updateConfiguration(configKey, updated);
  };

  const handleChange = (key: string, val: string) => {
    const updated = { ...dict, [key]: val };
    handleUpdate(updated);
  };

  const handleDelete = (key: string) => {
    const updated = { ...dict };
    delete updated[key];
    handleUpdate(updated);
  };

  const handleAdd = () => {
    if (newKey.trim() === "") return;
    const updated = { ...dict, [newKey]: newValue };
    handleUpdate(updated);
    setNewKey("");
    setNewValue("");
  };

  return (
    <div>
      <Typography variant="subtitle2" gutterBottom>
        {label}
      </Typography>
      <Stack spacing={1}>
        {Object.entries(dict).map(([key, value]) => (
          <Stack key={key} direction="row" spacing={1} alignItems="center">
            <EditableSettingField
              configKey={`${configKey}.${key}`}
              label={key}
              value={value}
              onUpdate={(newVal) => {
                const updated = { ...dict, [key]: String(newVal) };
                setDict(updated);
                updateConfiguration(configKey, updated);
              }}
            />
            <IconButton onClick={() => handleDelete(key)} size="small">
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
