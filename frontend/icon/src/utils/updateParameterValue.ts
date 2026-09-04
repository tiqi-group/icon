import { runMethod } from "../socket";
import { ParameterValueType } from "../types/ExperimentMetadata";

export const updateParameterValue = (
  paramId: string,
  newValue: ParameterValueType,
  callback?: (ack: unknown) => void,
) => {
  runMethod("parameters.update_parameter_by_id", [paramId, newValue], {}, callback);
};
