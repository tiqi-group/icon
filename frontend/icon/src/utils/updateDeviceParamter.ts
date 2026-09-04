import { runMethod } from "../socket";
import { ParameterValueType } from "../types/ExperimentMetadata";
import { QuantityMap } from "../types/QuantityMap";

export const updateDeviceParameter = (
  deviceName: string,
  paramId: string,
  newValue: ParameterValueType | QuantityMap,
  paramType: "float" | "int" | "Quantity",
  callback?: (ack: unknown) => void,
) => {
  runMethod(
    "devices.update_parameter_value",
    [],
    { name: deviceName, parameter_id: paramId, new_value: newValue, type_: paramType },
    callback,
  );
};
