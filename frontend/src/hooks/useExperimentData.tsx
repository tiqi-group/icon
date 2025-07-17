import { useEffect, useState } from "react";
import { socket } from "../socket";
import { ExperimentData, ExperimentDataPoint } from "../types/ExperimentData";

/**
 * Subscribes to real-time experiment updates over a WebSocket and accumulates
 * shot data, result data, vector data, scan parameters, and sequence JSONs
 * indexed by shot index.
 *
 * - On mount (or jobId change): fetches initial state and sets up live listener.
 * - Accumulates incoming data by merging into current state.
 * - Appends to `json_sequences` only if the sequence differs from the last one.
 *
 * @param jobId - The job identifier to subscribe to. If undefined, no action is taken.
 * @returns The current ExperimentData object including accumulated data and sequence history.
 */
export function useExperimentData(jobId: string | undefined) {
  const [experimentData, setExperimentData] = useState<ExperimentData>({
    shot_channels: {},
    result_channels: {},
    vector_channels: {},
    scan_parameters: {},
    json_sequences: [],
  });

  useEffect(() => {
    if (!jobId) return;

    const eventName = `experiment_${jobId}`;

    const handleData = (data: ExperimentDataPoint) => {
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
    socket.emit("get_experiment_data", jobId, (data: ExperimentData) => {
      setExperimentData(data);
    });

    return () => {
      socket.off(eventName, handleData);
    };
  }, [jobId]);

  return experimentData;
}
