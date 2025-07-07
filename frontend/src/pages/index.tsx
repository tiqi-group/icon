import { useContext, useEffect, useState } from "react";
import { Box, Card, CardContent, Grid } from "@mui/material";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";
import { DeviceStatus } from "../types/enums";
import { runMethod, socket } from "../socket";
import { SerializedDict } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";
import { useConfiguration } from "../hooks/useConfiguration";
import { InfluxDBStatusCard } from "../components/statusCards/InfluxDBStatus";
import { HardwareStatusCard } from "../components/statusCards/HardwareStatus";
import { DevicesStatusCard } from "../components/statusCards/DevicesStatus";

interface Status {
  influxdb: boolean;
  hardware: boolean;
}

export default function DashboardPage() {
  const devices = useContext(DeviceInfoContext);
  const configuration = useConfiguration();

  const [influxReachable, setInfluxReachable] = useState<boolean>(false);
  const [hardwareReachable, setHardwareReachable] = useState<boolean>(false);

  useEffect(() => {
    runMethod("status.get_status", [], {}, (response) => {
      const status = deserialize(response as SerializedDict) as Status;
      setInfluxReachable(status.influxdb);
      setHardwareReachable(status.hardware);
    });

    socket.on("status.influxdb", (status: boolean) => setInfluxReachable(status));
    socket.on("status.hardware", (status: boolean) => setHardwareReachable(status));
    return () => {
      socket.off("status.influxdb");
      socket.off("status.hardware");
    };
  }, []);

  const enabledDevices = Object.entries(devices).filter(
    ([, d]) => d.status === DeviceStatus.ENABLED,
  );
  const disabledDevices = Object.entries(devices).filter(
    ([, d]) => d.status !== DeviceStatus.ENABLED,
  );

  return (
    <Box sx={{ p: 3 }}>
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
            <CardContent sx={{ display: "flex", flex: 1, alignItems: "center" }}>
              <HardwareStatusCard
                hardwareReachable={hardwareReachable}
                configuration={configuration}
              />
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
    </Box>
  );
}
