import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { ExperimentData, ExperimentDataPoint } from "../types/ExperimentData";
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

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExperimentData(emptyExperimentData);
    if (!jobId) return;

    const eventName = `experiment_${jobId}`;

    const handleData = (data: ExperimentDataPoint) => {
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
        };
      });
    };

    socket.on(eventName, handleData);

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
      socket.off(eventName, handleData);
    };
  }, [jobId]);

  return { experimentData, experimentDataError, loading };
}
