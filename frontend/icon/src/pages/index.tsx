import { useContext } from "react";
import { Card, CardContent, Grid } from "@mui/material";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { useConfiguration } from "../hooks/useConfiguration";
import { useSystemStatus } from "../hooks/useSystemStatus";
import { InfluxDBStatusCard } from "../components/statusCards/InfluxDBStatus";
import { HardwareStatusCard } from "../components/statusCards/HardwareStatus";
import { DevicesStatusCard } from "../components/statusCards/DevicesStatus";

export default function DashboardPage() {
  const devices = useContext(DeviceInfoContext);
  const configuration = useConfiguration();
  const { influxReachable, hardwareStatus } = useSystemStatus();

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
              }}
            >
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
