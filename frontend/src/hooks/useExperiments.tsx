import { useEffect, useState, useCallback } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { ExperimentDict } from "../types/ExperimentMetadata";

/**
 * React hook that provides access to experiment metadata.
 *
 * This hook:
 * - Fetches the full set of experiments from the backend using
 *   `experiments.get_experiments`.
 * - Subscribes to `experiments.update` socket events to refresh data
 *   when the backend notifies of changes.
 * - Cleans up the socket listener on unmount.
 *
 * @returns The current experiment metadata as an ExperimentDict.
 */
export function useExperiments(): ExperimentDict {
  const [experiments, setExperiments] = useState<ExperimentDict>({});

  const fetchExperiments = useCallback(() => {
    runMethod("experiments.get_experiments", [], {}, (ack) => {
      setExperiments(deserialize(ack as SerializedObject) as ExperimentDict);
    });
  }, []);

  useEffect(() => {
    fetchExperiments();
    socket.on("experiments.update", fetchExperiments);

    return () => {
      socket.off("experiments.update", fetchExperiments);
    };
  }, [fetchExperiments]);

  return experiments;
}
