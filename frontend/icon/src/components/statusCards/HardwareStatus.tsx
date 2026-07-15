import { Typography, Stack, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Link as RouterLink } from "react-router";
import { HardwareError } from "../../types/HardwareStatus";

interface HardwareStatusCardProps {
  hardwareStatus: boolean | HardwareError;
  configuration: {
    id: string;
    args: Record<string, string | number>;
    enabled: boolean;
  };
}

export const HardwareStatusCard = ({
  hardwareStatus,
  configuration,
}: HardwareStatusCardProps) => (
  <Stack spacing={1}>
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <ReachabilityIndicator enabled={configuration.enabled} status={hardwareStatus} />
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
    {Object.entries(configuration.args).map(([key, val]) => (
      <Typography variant="body2" key={key}>
        {key}: {val}
      </Typography>
    ))}
  </Stack>
);
