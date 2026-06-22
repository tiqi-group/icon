import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import {
  ExperimentData,
  ExperimentDataPoint,
  ExperimentDeviceData,
  ExperimentDeviceDataPoint,
  FitResult,
  PlotWindows,
  ParameterValue,
} from "../types/ExperimentData";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";

const emptyExperimentData: ExperimentData = {
  device_data: [],
  scan_parameters: {},
  parameters: {},
  total_data_points: 0,
};

/**
 * Hook to fetch and subscribe to experiment data for a given job ID.
 *
 * - Fetches initial experiment data via RPC.
 * - Subscribes to live updates via WebSocket and merges new data.
 * - Updates hardware_instructions only when the sequence changes.
 * - Captures any fetch error in `experimentDataError`.
 *
 * @param jobId - The job ID to fetch and subscribe to.
 * @returns The current experiment data and any fetch error.
 */
export function useExperimentData(jobId: string | undefined) {
  const [experimentData, setExperimentData] =
    useState<ExperimentData>(emptyExperimentData);
  const [experimentDataError, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExperimentData(emptyExperimentData);
    if (!jobId) return;

    const dataPointEvent = `experiment_${jobId}`;

    const handleNewDataPoint = (data: ExperimentDataPoint) => {
      setError(null);
      setExperimentData((prev) => {
        const mergeDataPoint = (
          deviceData: ExperimentDeviceData,
          dev: ExperimentDeviceDataPoint,
        ) => {
          for (const [channel, value] of Object.entries(dev.readouts.shot_channels)) {
            (deviceData.readouts.shot_channels[channel] ??= {})[data.index] = value;
          }
          for (const [channel, value] of Object.entries(dev.readouts.result_channels)) {
            (deviceData.readouts.result_channels[channel] ??= {})[data.index] = value;
          }
          for (const [channel, value] of Object.entries(dev.readouts.vector_channels)) {
            (deviceData.readouts.vector_channels[channel] ??= {})[data.index] = value;
          }
          const lastEntry = deviceData.hardware_instructions.at(-1);
          if (!lastEntry || lastEntry[1] !== dev.hardware_instructions) {
            deviceData.hardware_instructions.push([
              data.index,
              dev.hardware_instructions,
            ]);
          }
          return deviceData;
        };

        const scan_parameters = { ...prev.scan_parameters };
        for (const [param, value] of Object.entries(data.scan_params)) {
          (scan_parameters[param] ??= {})[data.index] = value;
        }
        (scan_parameters["timestamp"] ??= {})[data.index] = data.timestamp;

        return {
          ...prev,
          device_data: mergeDeviceData(
            prev.device_data,
            data.device_data.map((dataPoint) => [dataPoint.device_id, dataPoint]),
            mergeDataPoint,
          ),
          scan_parameters,
          total_data_points: prev.total_data_points + 1,
        };
      });
    };

    const metadataEvent = `experiment_${jobId}_metadata`;

    const handleMetadata = (
      data: {
        device_id: string;
        readout_metadata: PlotWindows;
      }[],
    ) => {
      console.info("Got experiment metadata");
      const mergePlotWindows = (
        deviceData: ExperimentDeviceData,
        plot_windows: PlotWindows,
      ) => {
        console.info(plot_windows);
        return { ...deviceData, plot_windows };
      };
      setExperimentData((prev) => {
        return {
          ...prev,
          device_data: mergeDeviceData(
            prev.device_data,
            data.map(({ device_id, readout_metadata }) => [
              device_id,
              readout_metadata,
            ]),
            mergePlotWindows,
          ),
        };
      });
    };

    const parameterValueEvent = `experiment_params_${jobId}`;
    const handleValueEvent = (valueUpdates: Record<string, ParameterValue>) => {
      setExperimentData((prev) => {
        return { ...prev, parameters: { ...prev.parameters, ...valueUpdates } };
      });
    };

    const fitEvent = `experiment_fit_${jobId}`;
    type Add = { fit_data: FitResult; device_id: string };
    type Delete = { deleted: boolean; result_channel: string; device_id: string };
    function isDelete(data: Add | Delete): data is Delete {
      return "deleted" in data;
    }
    const handleFitEvent = (data: Add | Delete) => {
      setExperimentData((prev) => {
        return {
          ...prev,
          device_data: prev.device_data.map((dev) => {
            if (dev.device_id != data.device_id) return dev;
            if (isDelete(data)) {
              const { [data.result_channel]: _removed, ...rest } = dev.fits;
              void _removed;
              return { ...dev, fits: rest };
            }
            return {
              ...dev,
              fits: { ...dev.fits, [data.fit_data.result_channel]: data.fit_data },
            };
          }),
        };
      });
    };

    socket.on(dataPointEvent, handleNewDataPoint);
    socket.on(metadataEvent, handleMetadata);
    socket.on(parameterValueEvent, handleValueEvent);
    socket.on(fitEvent, handleFitEvent);

    runMethod("data.get_experiment_data_by_job_id", [], { job_id: jobId }, (ack) => {
      const deserialized = deserialize(ack as SerializedObject) as
        | Error
        | ExperimentData;

      if (deserialized instanceof Error) {
        console.info("Failed to fetch job run:", deserialized);
        setError(deserialized);
      } else {
        setExperimentData(deserialized);
      }
      setLoading(false);
    });

    return () => {
      socket.off(dataPointEvent, handleNewDataPoint);
      socket.off(metadataEvent, handleMetadata);
      socket.off(parameterValueEvent, handleValueEvent);
      socket.off(fitEvent, handleFitEvent);
    };
  }, [jobId]);

  return { experimentData, experimentDataError, loading };
}

function mergeDeviceData<T>(
  deviceData: ExperimentDeviceData[],
  data: [string, T][],
  merge: (dev: ExperimentDeviceData, d: T) => ExperimentDeviceData,
) {
  const deviceDataById = Object.fromEntries(
    deviceData.map((dev) => [dev.device_id, structuredClone(dev)]),
  );
  for (const [devId, dev] of data) {
    deviceDataById[devId] = merge(
      deviceDataById[devId] ?? defaultDeviceData(devId),
      dev,
    );
  }
  return Object.values(deviceDataById);
}

function defaultDeviceData(deviceId: string) {
  return {
    device_id: deviceId,
    readouts: { result_channels: {}, vector_channels: {}, shot_channels: {} },
    plot_windows: {
      result_channels: [],
      vector_channels: [],
      shot_channels: [],
    },
    hardware_instructions: [],
  };
}
