import { useCallback, useContext, useSyncExternalStore } from "react";
import { ParameterValueType } from "../types/ExperimentMetadata";
import { ParameterStoreContext } from "../contexts/ParameterStoreContext";

/**
 * React hook to access and update a single parameter value from the parameter store.
 *
 * This hook uses `useSyncExternalStore` to subscribe to changes in a specific parameter.
 * It ensures that the component re-renders only when the value for the given key changes.
 *
 * @param key - The parameter ID to read and subscribe to.
 * @returns A tuple: [current value, setter function to update the value].
 *
 * @throws If the hook is used outside of a `ParameterStoreProvider`.
 */
export function useParameter(
  key: string,
): [ParameterValueType | undefined, (value: ParameterValueType) => void] {
  const store = useContext(ParameterStoreContext);
  if (!store) throw new Error("No ParameterStoreContext");

  const value = useSyncExternalStore(
    (cb) => store.subscribe(key, cb),
    () => store.get(key),
  );

  const setValue = useCallback(
    (v: ParameterValueType) => {
      store.set(key, v);
    },
    [store, key],
  );

  return [value, setValue];
}
