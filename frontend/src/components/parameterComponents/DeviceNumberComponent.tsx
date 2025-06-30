import React, { useContext, useEffect, useState } from "react";
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

interface DeviceNumberComponentProps {
  deviceName: string;
  paramId: string;
  onContextMenu?: (e: React.MouseEvent, id: string) => void;
}

export const DeviceNumberComponent = ({
  deviceName,
  paramId,
  onContextMenu,
}: DeviceNumberComponentProps) => {
  const state = useContext(DeviceStateContext);
  if (state === null) return null;

  const [error, setError] = useState(false);

  const rawValue = getNestedDictByPath(
    state.value as unknown as Record<string, SerializedObject>,
    paramId,
  ) as SerializedFloat | SerializedInteger | SerializedQuantity;
  const type = rawValue["type"];
  let value: string;

  if (type == "Quantity") {
    value = String(rawValue["value"]["magnitude"]);
  } else {
    value = String(rawValue["value"]);
  }
  const [inputValue, setInputValue] = useState(value);

  const handleChange = (val: string) => {
    setInputValue(val);
  };

  const handleBlur = (val: string) => {
    const parsed = parseFloat(val);

    const devicePrefix = `devices.device_proxies["${deviceName}"].`;
    const accessPath = paramId.startsWith(devicePrefix)
      ? paramId.slice(devicePrefix.length)
      : paramId;

    if (numberValid(val, Number.NEGATIVE_INFINITY, Number.POSITIVE_INFINITY)) {
      if (type == "Quantity") {
        updateDeviceParameter(
          deviceName,
          accessPath,
          { magnitude: parsed, unit: rawValue["value"]["unit"] },
          type,
        );
      } else {
        updateDeviceParameter(deviceName, accessPath, parsed, type);
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
      onContextMenu={onContextMenu}
    />
  );
};
