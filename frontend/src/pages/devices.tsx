import { useContext, useState } from "react";
import {
  Box,
  Typography,
  Divider,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  MenuItem,
} from "@mui/material";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { DeviceInfo } from "../types/DeviceInfo";
import { runMethod } from "../socket";
import { Device } from "../components/devices/Device";
import { Tabs, Tab } from "@mui/material";

const DeviceGroup = ({
  title,
  devices,
  view,
}: {
  title: string;
  devices: [string, DeviceInfo][];
  view: "scannable" | "pydase";
}) => (
  <Box sx={{ mb: 4 }}>
    <Typography variant="h6" gutterBottom>
      {title}
    </Typography>
    {devices.length === 0 ? (
      <Typography variant="body2" color="text.secondary">
        No devices
      </Typography>
    ) : (
      devices.map(([name, info]) => (
        <Device
          key={name}
          name={name}
          url={info.url}
          status={info.status}
          description={info.description}
          retry_attempts={info.retry_attempts}
          retry_delay_seconds={info.retry_delay_seconds}
          reachable={info.reachable}
          view={view}
        />
      ))
    )}
    <Divider sx={{ mt: 2 }} />
  </Box>
);

const AddDeviceDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
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

const DevicesPage = () => {
  const devices = useContext(DeviceInfoContext);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deviceView, setDeviceView] = useState<"scannable" | "pydase">("scannable");

  const entries = Object.entries(devices);
  const enabled = entries.filter(([, d]) => d.status === DeviceStatus.ENABLED);
  const disabled = entries.filter(([, d]) => d.status !== DeviceStatus.ENABLED);

  return (
    <Box sx={{ p: 2 }}>
      <Tabs
        value={deviceView}
        onChange={(_, newValue) => setDeviceView(newValue)}
        sx={{ mb: 2 }}
      >
        <Tab label="Scannable Parameters" value="scannable" />
        <Tab label="Pydase Interface" value="pydase" />
      </Tabs>

      <Button variant="contained" sx={{ mb: 2 }} onClick={() => setDialogOpen(true)}>
        Add Device
      </Button>
      <AddDeviceDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
      <DeviceGroup title="Enabled Devices" devices={enabled} view={deviceView} />
      <DeviceGroup title="Disabled Devices" devices={disabled} view={deviceView} />
    </Box>
  );
};

export default DevicesPage;
