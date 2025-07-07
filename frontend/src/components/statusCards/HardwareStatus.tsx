import { Box, Typography, Stack } from "@mui/material";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Configuration } from "../../types/Configuration";

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
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <ReachabilityIndicator enabled reachable={hardwareReachable} />
        <Typography variant="h6">Hardware</Typography>
      </Box>
      <Typography variant="body2">Host: {host}</Typography>
      <Typography variant="body2">Port: {port}</Typography>
    </Stack>
  );
};
