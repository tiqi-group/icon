import { useContext, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Grid,
  IconButton,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { useConfiguration } from "../hooks/useConfiguration";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { InfluxDBStatusCard } from "../components/statusCards/InfluxDBStatus";
import {
  HardwareStatus,
  HardwareStatusCard,
} from "../components/statusCards/HardwareStatus";
import { DevicesStatusCard } from "../components/statusCards/DevicesStatus";

export default function DashboardPage() {
  const devices = useContext(DeviceInfoContext);
  const configuration = useConfiguration();
  const { influxReachable, hardwareStatus, refresh } = useSystemStatus();

  const [refreshingSince, setRefreshingSince] = useState<HardwareStatus[] | null>(null);
  const refreshing = refreshingSince === hardwareStatus;
  const handleRefresh = () => {
    setRefreshingSince(hardwareStatus);
    refresh();
  };

  const enabledDevices = Object.entries(devices).filter(
    ([, d]) => d.status === DeviceStatus.ENABLED,
  );
  const disabledDevices = Object.entries(devices).filter(
    ([, d]) => d.status !== DeviceStatus.ENABLED,
  );

  return (
    <div style={{ padding: 24 }}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent sx={{ display: "flex", flex: 1, alignItems: "center" }}>
              <InfluxDBStatusCard
                influxReachable={influxReachable}
                configuration={configuration}
              />
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
          <Card>
            <CardContent
              sx={{
                display: "flex",
                flex: 1,
                flexDirection: "column",
                gap: "1.5em",
                position: "relative",
              }}
            >
              <Box sx={{ position: "absolute", top: 8, right: 8 }}>
                {refreshing ? (
                  <Box sx={{ display: "flex", padding: 1 }}>
                    <CircularProgress size={24} aria-label="Refreshing status" />
                  </Box>
                ) : (
                  <IconButton title="Refresh status" onClick={handleRefresh}>
                    <RefreshIcon />
                  </IconButton>
                )}
              </Box>
              {hardwareStatus.map((dev) => (
                <HardwareStatusCard device={dev} />
              ))}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ sm: 12, md: 6 }}>
          <Card>
            <CardContent sx={{ position: "relative" }}>
              <DevicesStatusCard
                enabledDevices={enabledDevices}
                disabledDevices={disabledDevices}
              />
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </div>
  );
}
