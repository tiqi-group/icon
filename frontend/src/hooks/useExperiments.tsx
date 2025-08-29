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
  }, [fetchExperiments]);

  return experiments;
}
