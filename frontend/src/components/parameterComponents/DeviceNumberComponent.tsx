import { useContext, useEffect, useState } from "react";
import { DeviceStateContext } from "../../contexts/DeviceStateContext";
import { BaseNumberComponent, numberValid } from "./BaseNumberComponent";
import { updateDeviceParameter } from "../../utils/updateDeviceParamter";
import { getNestedDictByPath } from "../../utils/stateUtils";
import {
  SerializedFloat,
  SerializedInteger,
  SerializedObject,
  SerializedQuantity,
} from "../../types/SerializedObject";
import { useScanContext } from "../../hooks/useScanContext";

interface DeviceNumberComponentProps {
  deviceName: string;
  paramId: string;
  scanIndex: number | null;
}

export const DeviceNumberComponent = ({
  deviceName,
  paramId,
  scanIndex,
}: DeviceNumberComponentProps) => {
  const { handleRightClick } = useScanContext();
  const state = useContext(DeviceStateContext);
  const [error, setError] = useState(false);
  const [inputValue, setInputValue] = useState("");

  const devicePrefix = `devices.device_proxies["${deviceName}"].`;
  const accessPath = paramId.startsWith(devicePrefix)
    ? paramId.slice(devicePrefix.length)
    : paramId;

  let rawValue: SerializedFloat | SerializedInteger | SerializedQuantity | null = null;

  if (state === null) return null;

  let value = "";
  try {
    rawValue = getNestedDictByPath(
      state.value as unknown as Record<string, SerializedObject>,
      paramId,
    ) as SerializedFloat | SerializedInteger | SerializedQuantity;

    if (rawValue.type === "Quantity") {
      value = String(rawValue.value.magnitude);
    } else {
      value = String(rawValue.value);
    }
  } catch (err) {
    console.log(
      "Could not render DeviceNumberComponent. State is not yet up-to-date: ",
      err,
    );
  }

  useEffect(() => {
    setInputValue(value);
  }, [value]);

  if (rawValue === undefined || rawValue === null) return null;

  const handleChange = (val: string) => {
    setInputValue(val);
  };

  const handleBlur = (val: string) => {
    const parsed = parseFloat(val);

    if (numberValid(val, Number.NEGATIVE_INFINITY, Number.POSITIVE_INFINITY)) {
      if (rawValue.type == "Quantity") {
        updateDeviceParameter(
          deviceName,
          accessPath,
          { magnitude: parsed, unit: rawValue["value"]["unit"] },
          rawValue.type,
        );
      } else {
        updateDeviceParameter(deviceName, accessPath, parsed, rawValue.type);
      }
      setError(false);
    } else {
      setError(true);
    }
  };

  return (
    <BaseNumberComponent
      id={paramId}
      displayName={paramId}
      value={inputValue}
      error={error}
      onChange={handleChange}
      onBlur={handleBlur}
      onContextMenu={(event) =>
        handleRightClick(event, accessPath, deviceName, "Devices")
      }
      inputBackgroundColor={scanIndex !== null ? "#186fc67e" : undefined}
      title={scanIndex !== null ? `Scan parameter ${scanIndex + 1}` : undefined}
    />
  );
};
