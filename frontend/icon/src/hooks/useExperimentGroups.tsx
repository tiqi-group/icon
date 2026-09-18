import { useCallback, useEffect, useState } from "react";
import {
  ExperimentGroupsState,
  parseExperimentGroupsState,
} from "../utils/experimentGroups";

const STORAGE_KEY = "experimentGroups";

const readState = () => parseExperimentGroupsState(localStorage.getItem(STORAGE_KEY));

/**
 * Hook to manage the experiment groups stored in localStorage.
 *
 * @returns The current state and a function applying an update to the stored state.
 */
export function useExperimentGroups() {
  const [state, setState] = useState<ExperimentGroupsState>(readState);

  // Keep state updated if another window changes the groups
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) setState(readState());
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  const update = useCallback(
    (fn: (state: ExperimentGroupsState) => ExperimentGroupsState) => {
      const next = fn(readState());
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      setState(next);
    },
    [],
  );

  return [state, update] as const;
}
