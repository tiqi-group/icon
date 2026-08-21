import { ScanInfoState } from "../hooks/useScanInfoState";
import { runMethod } from "../socket";
import { SerializedInteger } from "../types/SerializedObject";
import { ScanPattern } from "../types/ScanParameterInfo";
import { deserialize } from "./deserializer";
import { ScanParameterBounds } from "./scanUtils";
import { openJobWindow } from "./windowUtils";

interface ScanParameterArgument {
  id?: string;
  values?: number[];
  device_name?: string;
  n_scan_points?: number;
}

const generateScanValues = (
  start: number,
  stop: number,
  points: number,
  pattern: ScanPattern,
) => {
  const linspace = (n: number) =>
    Array.from({ length: n }, (_, i) => start + (i * (stop - start)) / (n - 1));

  switch (pattern) {
    case "linear":
      return linspace(points);
    case "scatter":
      return linspace(points).sort(() => Math.random() - 0.5);
    case "centred": {
      const base = linspace(points);
      const mid = Math.floor((points - 1) / 2);
      const order = [mid];
      for (let k = 1; order.length < points; k++) {
        if (mid - k >= 0) order.push(mid - k);
        if (mid + k < points) order.push(mid + k);
      }
      return order.map((i) => base[i]);
    }
    case "forwardReverse": {
      const base = linspace(points);
      return [...base, ...base.reverse()];
    }
  }
};

const clampToBounds = (value: number, bounds: ScanParameterBounds): number => {
  if (bounds.min !== null && value < bounds.min) return bounds.min;
  if (bounds.max !== null && value > bounds.max) return bounds.max;
  return value;
};

export const submitJob = (
  experimentId: string,
  scanInfoState: ScanInfoState,
  parameterBounds: ScanParameterBounds[] = [],
): { clampedParamIds: string[] } => {
  const clampedParamIds: string[] = [];

  const scan_parameters = scanInfoState.parameters.map(
    ({ namespace, generation, deviceNameOrDisplayGroup, ...rest }, index) => {
      const param: ScanParameterArgument = { ...rest };
      if (namespace == "Real Time") {
        delete param.id;
      } else {
        delete param.n_scan_points;
        if (namespace == "Devices") {
          param.device_name = deviceNameOrDisplayGroup;
        }
        const bounds = parameterBounds[index] ?? { min: null, max: null };
        const clampedStart = clampToBounds(generation.start, bounds);
        const clampedStop = clampToBounds(generation.stop, bounds);
        if (clampedStart !== generation.start || clampedStop !== generation.stop) {
          clampedParamIds.push(rest.id);
        }
        param.values = generateScanValues(
          clampedStart,
          clampedStop,
          generation.points,
          generation.pattern,
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
    },
    (ack) => {
      const jobId = deserialize(ack as SerializedInteger);
      if (localStorage.getItem("openExperimentWindows") !== "false") {
        openJobWindow(jobId, experimentId);
      }
    },
  );

  return { clampedParamIds };
};
