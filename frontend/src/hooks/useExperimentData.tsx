import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import {
  ExperimentData,
  ExperimentDataPoint,
  FitResult,
  ParameterValue,
} from "../types/ExperimentData";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";

const emptyExperimentData: ExperimentData = {
  plot_windows: {
    result_channels: [],
    shot_channels: [],
    vector_channels: [],
  },
  shot_channels: {},
  result_channels: {},
  vector_channels: {},
  scan_parameters: {},
  json_sequences: [],
  parameters: {},
  total_data_points: 0,
  fits: {},
};

/**
 * Hook to fetch and subscribe to experiment data for a given job ID.
 *
 * - Fetches initial experiment data via RPC.
 * - Subscribes to live updates via WebSocket and merges new data.
 * - Updates json_sequences only when the sequence changes.
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
  const [latestShotData, setLatestShotData] = useState<Record<string, number[]>>({});
  const [resultBounds, setResultBounds] = useState({ min: Infinity, max: -Infinity });

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExperimentData(emptyExperimentData);
    setLatestShotData({});
    setResultBounds({ min: Infinity, max: -Infinity });
    if (!jobId) return;

    const dataPointEvent = `experiment_${jobId}`;

    const handleNewDataPoint = (data: ExperimentDataPoint) => {
      setError(null);
      setExperimentData((prev) => {
        const shot_channels = { ...prev.shot_channels };
        for (const [channel, value] of Object.entries(data.shot_channels)) {
          (shot_channels[channel] ??= {})[data.index] = value;
        }

        const result_channels = { ...prev.result_channels };
        for (const [channel, value] of Object.entries(data.result_channels)) {
          (result_channels[channel] ??= {})[data.index] = value;
        }

        const vector_channels = { ...prev.vector_channels };
        for (const [channel, value] of Object.entries(data.vector_channels)) {
          (vector_channels[channel] ??= {})[data.index] = value;
        }

        const scan_parameters = { ...prev.scan_parameters };
        for (const [param, value] of Object.entries(data.scan_params)) {
          (scan_parameters[param] ??= {})[data.index] = value;
        }
        (scan_parameters["timestamp"] ??= {})[data.index] = data.timestamp;

        const json_sequences = [...prev.json_sequences];
        const lastEntry = json_sequences.at(-1);
        if (!lastEntry || lastEntry[1] !== data.sequence_json) {
          json_sequences.push([data.index, data.sequence_json]);
        }

        return {
          ...prev,
          shot_channels,
          result_channels,
          vector_channels,
          scan_parameters,
          json_sequences,
          total_data_points: prev.total_data_points + 1,
        };
      });
      if (Object.keys(data.shot_channels).length > 0) {
        setLatestShotData((prev) => ({ ...prev, ...data.shot_channels }));
      }
      setResultBounds((prev) => {
        let { min, max } = prev;
        for (const value of Object.values(data.result_channels)) {
          if (Number.isFinite(value)) {
            if (value < min) min = value as number;
            if (value > max) max = value as number;
          }
        }
        return min === prev.min && max === prev.max ? prev : { min, max };
      });
    };

    const metadataEvent = `experiment_${jobId}_metadata`;

    const handleMetadata = (data: {
      readout_metadata: ExperimentData["plot_windows"];
    }) => {
      console.info("Got experiment metadata");
      console.info(data.readout_metadata);
      setExperimentData((prev) => {
        return { ...prev, plot_windows: data.readout_metadata };
      });
    };

    const parameterValueEvent = `experiment_params_${jobId}`;
    const handleValueEvent = (valueUpdates: Record<string, ParameterValue>) => {
      setExperimentData((prev) => {
        return { ...prev, parameters: { ...prev.parameters, ...valueUpdates } };
      });
    };

    const fitEvent = `experiment_fit_${jobId}`;
    const handleFitEvent = (data: FitResult & { deleted?: boolean }) => {
      setExperimentData((prev) => {
        if (data.deleted) {
          const { [data.result_channel]: _removed, ...rest } = prev.fits;
          void _removed;
          return { ...prev, fits: rest };
        }
        return {
          ...prev,
          fits: { ...prev.fits, [data.result_channel]: data },
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
        const latestShots: Record<string, number[]> = {};
        for (const [channel, groups] of Object.entries(deserialized.shot_channels)) {
          let latestIdx = -1;
          let latestArr: number[] | undefined;
          for (const [k, v] of Object.entries(groups)) {
            const n = parseInt(k, 10);
            if (n > latestIdx) { latestIdx = n; latestArr = v as number[]; }
          }
          if (latestArr !== undefined) latestShots[channel] = latestArr;
        }
        setLatestShotData(latestShots);

        let min = Infinity, max = -Infinity;
        for (const channelData of Object.values(deserialized.result_channels)) {
          for (const v of Object.values(channelData) as number[]) {
            if (Number.isFinite(v)) {
              if (v < min) min = v;
              if (v > max) max = v;
            }
          }
        }
        setResultBounds({ min: Number.isFinite(min) ? min : 0, max: Number.isFinite(max) ? max : 0 });

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

  return { experimentData, experimentDataError, loading, latestShotData, resultBounds };
}
