import { ParameterValueType } from "../types/ExperimentMetadata";

export interface Store {
  get: (key: string) => ParameterValueType | undefined;
  set: (key: string, value: ParameterValueType) => void;
  subscribe: (key: string, callback: () => void) => () => void;
  bulkSet: (data: Record<string, ParameterValueType>) => void;
}

export const createParameterStore = (): Store => {
  /**
   * Internal state storage for parameter values.
   *
   * Keys are parameter IDs (strings), values are the latest parameter values.
   * Values are of type `ParameterValueType`.
   */
  const state = new Map<string, ParameterValueType>();

  /**
   * Per-key subscriber map.
   *
   * For each parameter key, stores a set of subscriber callbacks.
   * These callbacks are invoked when the corresponding parameter value changes,
   * triggering `useSyncExternalStore` updates in subscribed components.
   */
  const listeners = new Map<string, Set<() => void>>();

  /**
   * Notifies all subscribers of the given key.
   *
   * This triggers the callbacks registered via `useSyncExternalStore.subscribe`.
   * React will then re-run `getSnapshot` and re-render components if needed.
   */
  const notify = (key: string) => {
    listeners.get(key)?.forEach((cb) => cb());
  };

  return {
    get: (key) => state.get(key) ?? undefined,

    set: (key, value) => {
      if (state.get(key) === value) return;
      state.set(key, value);
      notify(key);
    },

    subscribe: (key, callback) => {
      if (!listeners.has(key)) listeners.set(key, new Set());
      listeners.get(key)!.add(callback);

      // The subscribe function should return a function that cleans up the subscription.
      return () => listeners.get(key)?.delete(callback);
    },

    // Helper: replaces entire store (after initial load)
    bulkSet: (data: Record<string, ParameterValueType>) => {
      for (const [key, value] of Object.entries(data)) {
        state.set(key, value);
        notify(key);
      }
    },
  };
};
