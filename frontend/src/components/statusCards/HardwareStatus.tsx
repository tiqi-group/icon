import { Typography, Stack, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Link as RouterLink } from "react-router";

interface HardwareStatusCardProps {
  hardwareReachable: boolean;
  configuration: { id: string };
}

export const HardwareStatusCard = ({
  hardwareReachable,
  configuration,
}: HardwareStatusCardProps) => (
  <Stack spacing={1}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <ReachabilityIndicator enabled reachable={hardwareReachable} />
      <Typography variant="h6">{configuration.id}</Typography>

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
    {Object.entries(configuration)
      .filter(
        ([key, _]) => !["id", "controller_module", "controller_class"].includes(key),
      )
      .map(([key, val]) => (
        <Typography variant="body2">
          {key}: {val}
        </Typography>
      ))}
  </Stack>
);
