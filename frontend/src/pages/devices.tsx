import { useContext, useState } from "react";
import {
  Divider,
  Button,
  Switch,
  List,
  ListSubheader,
  ListItemText,
  Typography,
  ListItemButton,
} from "@mui/material";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { Device } from "../components/devices/Device";
import { ReachabilityIndicator } from "../components/devices/ReachabilityIndicator";
import { AddDeviceDialog } from "../components/devices/AddDeviceDialog";

const DevicesPage = () => {
  const devices = useContext(DeviceInfoContext);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deviceView, setDeviceView] = useState<"scannable" | "pydase">("scannable");
  const [selectedDeviceName, setSelectedDeviceName] = useState<string | null>(null);

  const entries = Object.entries(devices);
  const enabled = entries.filter(([, d]) => d.status === DeviceStatus.ENABLED);
  const disabled = entries.filter(([, d]) => d.status !== DeviceStatus.ENABLED);

  const selectedDevice = selectedDeviceName ? devices[selectedDeviceName] : null;

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          flexShrink: 0,
          width: 300,
          height: "100%",
          overflowY: "auto",
          borderRight: "1px solid var(--mui-palette-divider)",
        }}
      >
        <div
          style={{
            position: "sticky",
            borderBottom: "1px solid var(--mui-palette-divider)",
            padding: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <div style={{ fontSize: 14, minWidth: 64, textAlign: "right" }}>
            Scannable params
          </div>
          <Switch
            checked={deviceView === "pydase"}
            onChange={(e) => setDeviceView(e.target.checked ? "pydase" : "scannable")}
          />
          <div style={{ fontSize: 14, minWidth: 48 }}>pydase interface</div>
        </div>

        {enabled.length !== 0 && (
          <List subheader={<ListSubheader>Enabled Devices</ListSubheader>} dense>
            {enabled.map(([name, info]) => (
              <ListItemButton
                key={name}
                selected={selectedDeviceName === name}
                onClick={() => setSelectedDeviceName(name)}
              >
                <div style={{ display: "flex", alignItems: "center" }}>
                  <ReachabilityIndicator
                    enabled={info.status === DeviceStatus.ENABLED}
                    reachable={info.reachable}
                  />
                  <ListItemText primary={name} />
                </div>
              </ListItemButton>
            ))}
          </List>
        )}

        <Divider />

        {disabled.length !== 0 && (
          <List subheader={<ListSubheader>Disabled Devices</ListSubheader>} dense>
            {disabled.map(([name, info]) => (
              <ListItemButton
                key={name}
                selected={selectedDeviceName === name}
                onClick={() => setSelectedDeviceName(name)}
              >
                <div style={{ display: "flex", alignItems: "center" }}>
                  <ReachabilityIndicator
                    enabled={info.status === DeviceStatus.ENABLED}
                    reachable={info.reachable}
                  />
                  <ListItemText primary={name} />
                </div>
              </ListItemButton>
            ))}
          </List>
        )}

        <div style={{ display: "flex", justifyContent: "center", padding: 8 }}>
          <Button variant="contained" onClick={() => setDialogOpen(true)}>
            + Add Device
          </Button>
          <AddDeviceDialog open={dialogOpen} onClose={() => setDialogOpen(false)} />
        </div>
      </div>

      <div style={{ padding: 24, flexGrow: 1, overflow: "auto" }}>
        {selectedDevice ? (
          <Device
            name={selectedDeviceName!}
            url={selectedDevice.url}
            status={selectedDevice.status}
            description={selectedDevice.description}
            retry_attempts={selectedDevice.retry_attempts}
            retry_delay_seconds={selectedDevice.retry_delay_seconds}
            reachable={selectedDevice.reachable}
            view={deviceView}
          />
        ) : (
          <Typography variant="body1">Select a device to view details.</Typography>
        )}
      </div>
    </div>
  );
};

export default DevicesPage;
