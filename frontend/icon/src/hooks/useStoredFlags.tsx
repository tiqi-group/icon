import { useCallback, useMemo, useSyncExternalStore } from "react";
import { notifyStorageChange, subscribeToStorage } from "../utils/storageSubscription";

const parseNames = (raw: string | null): string[] => {
  try {
    const parsed: unknown = JSON.parse(raw ?? "[]");
    if (Array.isArray(parsed)) return parsed.filter((name) => typeof name === "string");
  } catch {
    // fall through
  }
  return [];
};

const setFlag = (key: string, name: string, value: boolean) => {
  const names = parseNames(localStorage.getItem(key));
  if (names.includes(name) === value) return;
  const next = value ? [...names, name] : names.filter((n) => n !== name);
  localStorage.setItem(key, JSON.stringify(next));
  notifyStorageChange();
};

/**
 * Hook to manage a set of named flags stored in localStorage, e.g. which sections
 * are expanded. Only the names of the flags that are set are stored.
 *
 * @param key The localStorage key
 * @returns A function telling whether a flag is set, one setting it, and the names of
 *   the flags that are set
 */
export function useStoredFlags(key: string) {
  const raw = useSyncExternalStore(subscribeToStorage, () => localStorage.getItem(key));
  const names = useMemo(() => parseNames(raw), [raw]);
  const isSet = useCallback((name: string) => names.includes(name), [names]);
  const set = useCallback(
    (name: string, value: boolean) => setFlag(key, name, value),
    [key],
  );

  return [isSet, set, names] as const;
}

/**
 * Same as useStoredFlags for a single flag. Re-renders only when that flag
 * changes, not when another flag of the set does.
 */
export function useStoredFlag(key: string, name: string) {
  const value = useSyncExternalStore(subscribeToStorage, () =>
    parseNames(localStorage.getItem(key)).includes(name),
  );
  const set = useCallback(
    (newValue: boolean) => setFlag(key, name, newValue),
    [key, name],
  );

  return [value, set] as const;
}
