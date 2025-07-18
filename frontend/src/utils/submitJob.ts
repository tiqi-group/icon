import { ScanInfoState } from "../contexts/ScanProvider";
import { authority, forwardedProto, runMethod } from "../socket";
import { SerializedInteger } from "../types/SerializedObject";
import { deserialize } from "./deserializer";

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
      const url = `${forwardedProto}://${authority}/data/${jobId}`;
      console.log(url);
      window.open(
        url,
        "_blank",
        "toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=600,height=500,left=100,top=100",
      );
    },
  );
};
