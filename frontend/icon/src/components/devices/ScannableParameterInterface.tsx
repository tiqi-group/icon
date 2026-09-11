import { useContext, useReducer } from "react";
import {
  DeviceStateContext,
  deviceStateReducer,
} from "../../contexts/DeviceStateContext";
import { DeviceInfoContext } from "../../contexts/DeviceInfoContext";
import { DeviceStatus } from "../../types/enums";
import { DeviceInfo } from "../../types/DeviceInfo";
import { DeviceNumberComponent } from "../parameterComponents/DeviceNumberComponent";
import { getScanIndex } from "../../utils/scanUtils";
import { useScanContext } from "../../hooks/useScanContext";
import { useDeviceStateSync } from "../../hooks/useDevicesSync";

interface ScannableParameterInterfaceProps {
  name: string;
}

export const ScannableParameterInterface = ({
  name,
}: ScannableParameterInterfaceProps) => {
  const infoContext = useContext(DeviceInfoContext);
  const deviceInfo = infoContext?.[name];

  if (
    !deviceInfo ||
    deviceInfo.status === DeviceStatus.DISABLED ||
    !deviceInfo.scannable_params?.length
  ) {
    return null;
  }

  return <ScannableParameters key={deviceInfo.name} deviceInfo={deviceInfo} />;
};

const ScannableParameters = ({ deviceInfo }: { deviceInfo: DeviceInfo }) => {
  const { scannedParamKeys } = useScanContext();
  const [deviceStates, deviceStateDispatch] = useReducer(deviceStateReducer, null);
  useDeviceStateSync(deviceStateDispatch, deviceInfo.name);

  const deviceProxyState =
    deviceStates?.value?.devices?.value?.device_proxies?.value?.[deviceInfo.name];

  if (!deviceProxyState) return null;

  try {
    return (
      <DeviceStateContext.Provider value={deviceStates}>
        {deviceInfo.scannable_params.map((paramKey: string) => {
          const scanIndex = getScanIndex(paramKey, scannedParamKeys);

          return (
            <DeviceNumberComponent
              key={paramKey}
              deviceName={deviceInfo.name}
              paramId={paramKey}
              scanIndex={scanIndex}
            />
          );
        })}
      </DeviceStateContext.Provider>
    );
  } catch {
    return null;
  }
};
