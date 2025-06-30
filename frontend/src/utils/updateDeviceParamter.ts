import { runMethod } from "../socket";
import { ParameterValueType } from "../types/ExperimentMetadata";

export const updateDeviceParameter = (
  deviceName: string,
  paramId: string,
  newValue: ParameterValueType,
  paramType: "float" | "int" | "bool" | "str",
  callback?: (ack: unknown) => void,
) => {
  runMethod(
    "devices.update_parameter_value",
    [],
    { name: deviceName, parameter_id: paramId, new_value: newValue, type_: paramType },
    callback,
  );
};
