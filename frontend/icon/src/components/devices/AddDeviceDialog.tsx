import { useState } from "react";
import {
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from "@mui/material";
import {} from "@mui/material";
import { runMethod } from "../../socket";

export const AddDeviceDialog = ({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) => {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"enabled" | "disabled">("enabled");
  const [description, setDescription] = useState("");
  const [retryAttempts, setRetryAttempts] = useState(3);
  const [retryDelay, setRetryDelay] = useState(0.0);

  const handleSubmit = () => {
    runMethod("devices.add_device", [], {
      name,
      url,
      status,
      description: description || null,
      retry_attempts: retryAttempts,
      retry_delay_seconds: retryDelay,
    });
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>Add New Device</DialogTitle>
      <DialogContent>
        <TextField
          fullWidth
          margin="dense"
          label="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          fullWidth
          margin="dense"
          label="URL"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <TextField
          fullWidth
          margin="dense"
          select
          label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as "enabled" | "disabled")}
        >
          <MenuItem value="enabled">Enabled</MenuItem>
          <MenuItem value="disabled">Disabled</MenuItem>
        </TextField>
        <TextField
          fullWidth
          margin="dense"
          label="Description"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <TextField
          fullWidth
          margin="dense"
          label="Retry Attempts"
          type="number"
          value={retryAttempts}
          onChange={(e) => setRetryAttempts(parseInt(e.target.value))}
        />
        <TextField
          fullWidth
          margin="dense"
          label="Retry Delay (s)"
          type="number"
          value={retryDelay}
          onChange={(e) => setRetryDelay(parseFloat(e.target.value))}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button onClick={handleSubmit} disabled={!name || !url}>
          Add
        </Button>
      </DialogActions>
    </Dialog>
  );
};
