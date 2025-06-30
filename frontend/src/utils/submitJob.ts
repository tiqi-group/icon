import { ScanInfoState } from "../contexts/ScanContext";
import { runMethod } from "../socket";

interface ScanParameterArgument {
  id: string;
  values: number[];
  device_name?: string;
}

export const submitJob = (experimentId: string, scanInfoState: ScanInfoState) => {
  const scan_parameters = scanInfoState.parameters.map(
    /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
    ({ generation, device_name, ...rest }) => {
      const param: ScanParameterArgument = { ...rest };
      if (device_name !== undefined) {
        param.device_name = device_name;
      }
      return param;
    },
  );

  runMethod("scheduler.submit_job", [], {
    experiment_id: experimentId,
    scan_parameters,
    priority: scanInfoState.priority,
    number_of_shots: scanInfoState.shots,
    repetitions: scanInfoState.repetitions,
  });
};
