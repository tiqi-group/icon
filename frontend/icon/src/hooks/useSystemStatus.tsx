import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { SerializedDict } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";
import { HardwareStatus } from "../components/statusCards/HardwareStatus";

interface Status {
  influxdb: boolean;
  hardware: HardwareStatus[];
}

const requestRefresh = () => runMethod("status.request_refresh");

/**
 * Hook for the system status reported by the backend health check.
 *
 * @returns Whether InfluxDB is reachable, the status of each hardware device, and a
 *   function to request an immediate status check instead of waiting for the next one.
 */
export function useSystemStatus(): {
  influxReachable: boolean;
  hardwareStatus: HardwareStatus[];
  refresh: () => void;
} {
  const [influxReachable, setInfluxReachable] = useState<boolean>(false);
  const [hardwareStatus, setHardwareStatus] = useState<HardwareStatus[]>([]);

  useEffect(() => {
    runMethod("status.get_status", [], {}, (response) => {
      const status = deserialize(response as SerializedDict) as Status;
      setInfluxReachable(status.influxdb);
      setHardwareStatus(status.hardware);
    });

    const handleInfluxStatus = (status: boolean) => setInfluxReachable(status);
    const handleHardwareStatus = (status: HardwareStatus[]) =>
      setHardwareStatus(status);

    socket.on("status.influxdb", handleInfluxStatus);
    socket.on("status.hardware", handleHardwareStatus);
    return () => {
      socket.off("status.influxdb", handleInfluxStatus);
      socket.off("status.hardware", handleHardwareStatus);
    };
  }, []);

  return { influxReachable, hardwareStatus, refresh: requestRefresh };
}
