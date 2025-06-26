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

const ReachabilityIndicator = ({ reachable }: { reachable: boolean }) => (
  <Box
    component="span"
    sx={{
      display: "inline-block",
      width: 10,
      height: 10,
      borderRadius: "50%",
      bgcolor: reachable ? "green" : "red",
      mr: 1,
    }}
  />
);

const DeviceItem = ({ name, info }: { name: string; info: DeviceInfo }) => {
  const toggleStatus = () => {
    const newStatus = info.status === DeviceStatus.ENABLED ? "disabled" : "enabled";
    runMethod("devices.update_device", [], { name, status: newStatus });
  };

  return (
    <Box sx={{ mb: 1 }}>
      <Box sx={{ display: "flex", alignItems: "center" }}>
        {info.status === DeviceStatus.ENABLED && (
          <ReachabilityIndicator reachable={info.reachable} />
        )}
        <Typography component="span" sx={{ flexGrow: 1 }}>
          {name} ({info.url})
        </Typography>
        <Button
          size="small"
          variant="outlined"
          onClick={toggleStatus}
          sx={{ minWidth: "90px" }}
        >
          {info.status === DeviceStatus.ENABLED ? "Disable" : "Enable"}
        </Button>
      </Box>
      {info.description && (
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ pl: info.status === DeviceStatus.ENABLED ? 2 : 0 }}
        >
          {info.description}
        </Typography>
      )}
    </Box>
  );
};

const DeviceGroup = ({
  title,
  devices,
}: {
  title: string;
  devices: [string, DeviceInfo][];
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
      devices.map(([name, info]) => <DeviceItem key={name} name={name} info={info} />)
    )}
    <Divider sx={{ mt: 2 }} />
  </Box>
);

const AddDeviceDialog = ({ open, onClose }: { open: boolean; onClose: () => void }) => {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [status, setStatus] = useState<"enabled" | "disabled">("enabled");
  const [description, setDescription] = useState("");

  const handleSubmit = () => {
    runMethod("devices.add_device", [], {
      name,
      url,
      status,
      description: description || null,
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

  const entries = Object.entries(devices);
  const enabled = entries.filter(([, d]) => d.status === DeviceStatus.ENABLED);
  const disabled = entries.filter(([, d]) => d.status !== DeviceStatus.ENABLED);

  return (
    <Box sx={{ p: 2 }}>
      <Button variant="contained" sx={{ mb: 2 }} onClick={() => setDialogOpen(true)}>
        Add Device
      </Button>
      <AddDeviceDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
      <DeviceGroup title="Enabled Devices" devices={enabled} />
      <DeviceGroup title="Disabled Devices" devices={disabled} />
    </Box>
  );
};

export default DevicesPage;
