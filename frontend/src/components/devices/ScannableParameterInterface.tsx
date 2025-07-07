import { useContext } from "react";
import { DeviceStateContext } from "../../contexts/DeviceStateContext";
import { DeviceInfoContext } from "../../contexts/DeviceInfoContext";
import { DeviceStatus } from "../../types/enums";
import { DeviceNumberComponent } from "../parameterComponents/DeviceNumberComponent";
import { getScanIndex } from "../../utils/getScanIndex";
import { useScanContext } from "../../hooks/useScanContext";

interface ScannableParameterInterfaceProps {
  name: string;
}

export const ScannableParameterInterface = ({
  name,
}: ScannableParameterInterfaceProps) => {
  const { scannedParamKeys } = useScanContext();

  const stateContext = useContext(DeviceStateContext);
  const infoContext = useContext(DeviceInfoContext);
  const deviceInfo = infoContext?.[name];
  const deviceProxyState =
    stateContext?.value?.devices?.value?.device_proxies?.value?.[name];

  const scannableParams = deviceInfo?.scannable_params;

  const shouldRender =
    stateContext &&
    deviceProxyState &&
    deviceInfo.status !== DeviceStatus.DISABLED &&
    scannableParams.length > 0;

  if (!shouldRender) return null;

  try {
    return (
      <>
        {scannableParams.map((paramKey: string) => {
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
      </>
    );
  } catch {
    return null;
  }
};
