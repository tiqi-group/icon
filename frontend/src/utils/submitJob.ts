import { ScanInfoState } from "../hooks/useScanInfoState";
import { runMethod } from "../socket";
import { SerializedInteger } from "../types/SerializedObject";
import { deserialize } from "./deserializer";
import { openJobWindow } from "./windowUtils";

interface ScanParameterArgument {
  id: string;
  values: number[];
  device_name?: string;
}

export const submitJob = (experimentId: string, scanInfoState: ScanInfoState) => {
  const scan_parameters = scanInfoState.parameters.map(
    /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
    ({ namespace, generation, deviceNameOrDisplayGroup, ...rest }) => {
      const param: ScanParameterArgument = { ...rest };
      if (namespace == "Devices") {
        param.device_name = deviceNameOrDisplayGroup;
      }
      return param;
    },
  );

  runMethod(
    "scheduler.submit_job",
    [],
    {
      experiment_id: experimentId,
      scan_parameters,
      priority: scanInfoState.priority,
      number_of_shots: scanInfoState.shots,
      repetitions: scanInfoState.repetitions,
    },
    (ack) => {
      const jobId = deserialize(ack as SerializedInteger);
      openJobWindow(jobId, experimentId);
    },
  );
};
