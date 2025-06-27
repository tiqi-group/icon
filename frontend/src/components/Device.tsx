import { useContext } from "react";
import { DeviceStateContext } from "../contexts/DeviceStateContext";
import { DeviceInfoContext } from "../contexts/DeviceInfoContext";

interface DeviceProps {
  name: string;
}

export const Device = (props: DeviceProps) => {
  const stateContext = useContext(DeviceStateContext);
  const infoContext = useContext(DeviceInfoContext);
  const deviceInfo = infoContext[props.name];

  const serializedState =
    stateContext !== null
      ? stateContext["value"]["device_proxies"]["value"][props.name]
      : null;

  return (
    <>
      {props.name}: {serializedState !== null ? JSON.stringify(serializedState) : ""}
    </>
  );
};

Device.displayName = "Device";
