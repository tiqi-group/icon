import { Box, Typography, Stack } from "@mui/material";
import { ReachabilityIndicator } from "../devices/ReachabilityIndicator";
import { Configuration } from "../../pages";

interface InfluxDBStatusCardProps {
  influxReachable: boolean;
  configuration: Configuration;
}

export const InfluxDBStatusCard = ({
  influxReachable,
  configuration,
}: InfluxDBStatusCardProps) => {
  if (!("databases" in configuration)) {
    return <Typography variant="h6">InfluxDB</Typography>;
  }

  const { host, port, database } = configuration.databases.influxdbv1;

  return (
    <Stack spacing={1}>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
        <ReachabilityIndicator enabled reachable={influxReachable} />
        <Typography variant="h6">InfluxDB</Typography>
      </Box>
      <Typography variant="body2">Host: {host}</Typography>
      <Typography variant="body2">Port: {port}</Typography>
      <Typography variant="body2">Database: {database}</Typography>
    </Stack>
  );
};
