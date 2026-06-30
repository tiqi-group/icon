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

  const isV2 = configuration.databases.backend === "influxdbv2";

  return (
    <Stack spacing={1}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <ReachabilityIndicator enabled reachable={influxReachable} />
        <Typography variant="h6">InfluxDB {isV2 ? "v2" : "v1"}</Typography>
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
      {isV2 ? (
        <>
          <Typography variant="body2">URL: {configuration.databases.influxdbv2.url}</Typography>
          <Typography variant="body2">Org: {configuration.databases.influxdbv2.org}</Typography>
          <Typography variant="body2">Bucket: {configuration.databases.influxdbv2.bucket}</Typography>
        </>
      ) : (
        <>
          <Typography variant="body2">Host: {configuration.databases.influxdbv1.host}</Typography>
          <Typography variant="body2">Port: {configuration.databases.influxdbv1.port}</Typography>
          <Typography variant="body2">Database: {configuration.databases.influxdbv1.database}</Typography>
        </>
      )}
    </Stack>
  );
};
