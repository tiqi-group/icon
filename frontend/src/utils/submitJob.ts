import { ScanInfoState } from "../hooks/useScanInfoState";
import { runMethod } from "../socket";
import { ScanMode } from "../types/enums";
import { SerializedInteger } from "../types/SerializedObject";
import { deserialize } from "./deserializer";
import { generateScanValues, generateScatterOrder } from "./scanUtils";
import { openJobWindow } from "./windowUtils";

interface ScanParameterArgument {
  id?: string;
  values?: number[];
  device_name?: string;
  n_scan_points?: number;
}

export const submitJob = (experimentId: string, scanInfoState: ScanInfoState) => {
  // In a correlated scan, all parameters are stepped through in lockstep, so a
  // "scatter" pattern must scatter every parameter in the same order. Otherwise each
  // parameter would be independently shuffled and effectively paired at random.
  const steppedParameters = scanInfoState.parameters.filter(
    (p) => p.namespace !== "Real Time",
  );
  const sharedScatterOrder =
    scanInfoState.scanMode === ScanMode.CORRELATED && steppedParameters.length > 0
      ? generateScatterOrder(steppedParameters[0].generation.points)
      : undefined;

  const scan_parameters = scanInfoState.parameters.map(
    ({ namespace, generation, deviceNameOrDisplayGroup, ...rest }) => {
      const param: ScanParameterArgument = { ...rest };
      if (namespace == "Real Time") {
        delete param.id;
      } else {
        delete param.n_scan_points;
        if (namespace == "Devices") {
          param.device_name = deviceNameOrDisplayGroup;
        }
        param.values = generateScanValues(
          generation.start,
          generation.stop,
          generation.points,
          generation.pattern,
          sharedScatterOrder,
        );
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
      scan_mode: scanInfoState.scanMode,
    },
    (ack) => {
      const jobId = deserialize(ack as SerializedInteger);
      if (localStorage.getItem("openExperimentWindows") !== "false") {
        openJobWindow(jobId, experimentId);
      }
    },
  );
};
