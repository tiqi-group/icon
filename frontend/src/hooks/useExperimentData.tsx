import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { ExperimentData, ExperimentDataPoint } from "../types/ExperimentData";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";

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
  const [experimentData, setExperimentData] = useState<ExperimentData>({
    shot_channels: {},
    result_channels: {},
    vector_channels: {},
    scan_parameters: {},
    json_sequences: [],
  });
  const [experimentDataError, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!jobId) return;

    const eventName = `experiment_${jobId}`;

    const handleData = (data: ExperimentDataPoint) => {
      setError(null);
      setExperimentData((currentData) => {
        const newShot = { ...currentData.shot_channels };
        for (const channel of Object.keys(data.shot_channels)) {
          if (!(channel in newShot)) newShot[channel] = {};
          newShot[channel][data.index] = data.shot_channels[channel];
        }

        const newResult = { ...currentData.result_channels };
        for (const channel of Object.keys(data.result_channels)) {
          if (!(channel in newResult)) newResult[channel] = {};
          newResult[channel][data.index] = data.result_channels[channel];
        }

        const newVector = { ...currentData.vector_channels };
        for (const channel of Object.keys(data.vector_channels)) {
          if (!(channel in newVector)) newVector[channel] = {};
          newVector[channel][data.index] = data.vector_channels[channel];
        }

        const newScanParams = { ...currentData.scan_parameters };
        for (const scanParam of Object.keys(data.scan_params)) {
          if (!(scanParam in newScanParams)) newScanParams[scanParam] = {};
          newScanParams[scanParam][data.index] = data.scan_params[scanParam];
        }
        if (!("timestamp" in newScanParams)) newScanParams["timestamp"] = {};
        newScanParams.timestamp[data.index] = data.timestamp;

        const newJsonSequences = [...currentData.json_sequences];
        const lastEntry = newJsonSequences.at(-1);

        if (!lastEntry || lastEntry[1] !== data.sequence_json) {
          newJsonSequences.push([data.index, data.sequence_json]);
        }

        return {
          ...currentData,
          shot_channels: newShot,
          result_channels: newResult,
          vector_channels: newVector,
          scan_parameters: newScanParams,
          json_sequences: newJsonSequences,
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
        return;
      }

      setExperimentData(deserialized);
    });

    return () => {
      socket.off(eventName, handleData);
    };
  }, [jobId]);

  return { experimentData, experimentDataError };
}
