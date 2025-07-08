import { Typography, Stack, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Configuration } from "../../types/Configuration";
import { Link as RouterLink } from "react-router";

interface HardwareStatusCardProps {
  hardwareReachable: boolean;
  configuration: Configuration | null;
}

export const HardwareStatusCard = ({
  hardwareReachable,
  configuration,
}: HardwareStatusCardProps) => {
  if (configuration == null) {
    return <Typography variant="h6">Hardware</Typography>;
  }

  const { host, port } = configuration.hardware;

  return (
    <Stack spacing={1}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ReachabilityIndicator enabled reachable={hardwareReachable} />
        <Typography variant="h6">Hardware</Typography>

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
      <Typography variant="body2">Host: {host}</Typography>
      <Typography variant="body2">Port: {port}</Typography>
    </Stack>
  );
};
