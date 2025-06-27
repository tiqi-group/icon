import React, { useContext, useState } from "react";
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
import EditIcon from "@mui/icons-material/Edit";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { Device } from "../components/Device";
import { Tabs, Tab } from "@mui/material";

function websocketUrlToHttp(url: string): string {
  return url.replace(/^ws/, "http");
}
const ReachabilityIndicator = ({
  enabled,
  reachable,
}: {
  enabled: boolean;
  reachable: boolean;
}) => (
  <Box
    component="span"
    sx={{
      display: "inline-block",
      width: 10,
      height: 10,
      borderRadius: "50%",
      bgcolor: enabled ? (reachable ? "green" : "red") : "grey",
      mr: 1,
    }}
  />
);

const DeviceItem = React.memo(
  ({
    name,
    url,
    status,
    description,
    retry_attempts,
    retry_delay_seconds,
    reachable,
    view,
  }: {
    name: string;
    url: string;
    status: DeviceStatus;
    description: string | null;
    retry_attempts: number;
    retry_delay_seconds: number;
    reachable: boolean;
    view: "scannable" | "pydase";
  }) => {
    const [editingUrl, setEditingUrl] = useState(false);
    const infoContext = useContext(DeviceInfoContext);
    const deviceInfo = infoContext[name];

    const toggleStatus = () => {
      const newStatus = status === DeviceStatus.ENABLED ? "disabled" : "enabled";
      runMethod("devices.update_device", [], { name, status: newStatus });
    };

    const handleRetryAttemptsChange = (value: string) => {
      const parsed = parseInt(value);
      if (!Number.isNaN(parsed)) {
        runMethod("devices.update_device", [], {
          name,
          retry_attempts: parsed,
        });
      }
    };

    const handleRetryDelayChange = (value: string) => {
      const parsed = parseFloat(value);
      if (!Number.isNaN(parsed)) {
        runMethod("devices.update_device", [], {
          name,
          retry_delay_seconds: parsed,
        });
      }
    };

    const handleUrlSubmit = (newUrl: string) => {
      if (newUrl !== url) {
        runMethod("devices.update_device", [], {
          name,
          url: newUrl,
        });
      }
      setEditingUrl(false);
    };

    return (
      <Box sx={{ mb: 2 }}>
        <Box sx={{ display: "flex", alignItems: "center" }}>
          <ReachabilityIndicator
            enabled={status === DeviceStatus.ENABLED}
            reachable={reachable}
          />
          <Box
            sx={{
              flexGrow: 1,
              display: "flex",
              alignItems: "center",
              gap: 1,
              flexWrap: "wrap",
            }}
          >
            <Typography component="span" fontWeight="bold">
              {name}
            </Typography>

            {editingUrl ? (
              <TextField
                defaultValue={url}
                size="small"
                onBlur={(e) => handleUrlSubmit(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    handleUrlSubmit((e.target as HTMLInputElement).value);
                  } else if (e.key === "Escape") {
                    setEditingUrl(false);
                  }
                }}
                sx={{ width: "300px" }}
                autoFocus
              />
            ) : (
              <>
                <Typography component="span" color="text.secondary">
                  ({url}
                  <Tooltip
                    title={
                      status === DeviceStatus.ENABLED
                        ? "Disable the device to change the URL"
                        : "Edit URL"
                    }
                  >
                    <span>
                      <IconButton
                        size="small"
                        onClick={() => setEditingUrl(true)}
                        disabled={status === DeviceStatus.ENABLED}
                      >
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </span>
                  </Tooltip>
                  )
                </Typography>
              </>
            )}
          </Box>
          <Button
            size="small"
            variant="outlined"
            onClick={toggleStatus}
            sx={{ minWidth: "90px" }}
          >
            {status === DeviceStatus.ENABLED ? "Disable" : "Enable"}
          </Button>
        </Box>

        {description && (
          <Typography variant="body2" color="text.secondary" sx={{ pl: 2.4 }}>
            {description}
          </Typography>
        )}

        <Box sx={{ display: "flex", gap: 1, mt: 1 }}>
          <TextField
            label="Retry Attempts"
            size="small"
            type="number"
            defaultValue={retry_attempts}
            onBlur={(e) => handleRetryAttemptsChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRetryAttemptsChange((e.target as HTMLInputElement).value);
              }
            }}
            sx={{ width: "120px" }}
          />
          <TextField
            label="Retry Delay (s)"
            size="small"
            type="number"
            defaultValue={retry_delay_seconds}
            onBlur={(e) => handleRetryDelayChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                handleRetryDelayChange((e.target as HTMLInputElement).value);
              }
            }}
            sx={{ width: "140px" }}
          />
        </Box>
        {view === "scannable" ? (
          <Device name={name} />
        ) : deviceInfo.status === DeviceStatus.ENABLED ? (
          <iframe
            src={websocketUrlToHttp(deviceInfo.url)}
            style={{ width: "100%", height: "600px", border: "1px solid #ccc" }}
            title={`Pydase Interface for ${name}`}
          />
        ) : null}
      </Box>
    );
  },
);

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
        <DeviceItem
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
