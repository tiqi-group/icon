import { Typography, Stack, IconButton } from "@mui/material";
import EditIcon from "@mui/icons-material/Edit";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Configuration } from "../../types/Configuration";
import { Link as RouterLink } from "react-router";

interface InfluxDBStatusCardProps {
  influxReachable: boolean;
  configuration: Configuration | null;
}

export const InfluxDBStatusCard = ({
  influxReachable,
  configuration,
}: InfluxDBStatusCardProps) => {
  if (configuration == null) {
    return <Typography variant="h6">InfluxDB</Typography>;
  }

  const { host, port, database } = configuration.databases.influxdbv1;

  return (
    <Stack spacing={1}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ReachabilityIndicator enabled reachable={influxReachable} />
        <Typography variant="h6">InfluxDB</Typography>
        <IconButton
          component={RouterLink}
          to="/settings?tab=databases"
          sx={{ position: "relative" }}
          size="small"
          title="Open InfluxDB Settings"
          aria-label="Open InfluxDB Settings"
        >
          <EditIcon fontSize="small" />
        </IconButton>
      </div>
      <Typography variant="body2">Host: {host}</Typography>
      <Typography variant="body2">Port: {port}</Typography>
      <Typography variant="body2">Database: {database}</Typography>
    </Stack>
  );
};
