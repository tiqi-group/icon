import { Typography, Stack, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Link as RouterLink } from "react-router";

export interface HardwareStatus {
  display_name: string;
  args: [string, number | string | boolean][];
  enabled: boolean;
  reachable: boolean;
  error: string | null;
  warning: string | null;
}

interface HardwareStatusCardProps {
  device: HardwareStatus;
}

export const HardwareStatusCard = ({ device }: HardwareStatusCardProps) => (
  <Stack spacing={1}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <ReachabilityIndicator
        enabled={device.enabled}
        status={device.reachable}
        errorMsg={device.error}
      />
      <Typography variant="h6">{device.display_name}</Typography>

      <IconButton
        component={RouterLink}
        to="/settings?tab=hardware"
        sx={{ position: "relative" }}
        size="small"
        title="Open Hardware Settings"
        aria-label="Open Hardware Settings"
      >
        <EditIcon fontSize="small" />
      </IconButton>
    </div>
    {device.warning !== null && (
      <Typography variant="body2">⚠️ {device.warning}</Typography>
    )}
    {device.error !== null && (
      <Typography variant="body2">💥 {device.error}</Typography>
    )}
    {device.args.map(([key, val]) => (
      <Typography variant="body2" key={key}>
        {key}: {val}
      </Typography>
    ))}
  </Stack>
);
