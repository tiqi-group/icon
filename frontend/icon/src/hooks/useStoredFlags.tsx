import { useCallback, useMemo, useSyncExternalStore } from "react";

// Notifies hooks in this window; other windows get a storage event
const listeners = new Set<() => void>();

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
};

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
  listeners.forEach((listener) => listener());
};

/**
 * Hook to manage a set of named flags stored in localStorage, e.g. which sections
 * are expanded. Only the names of the flags that are set are stored.
 *
 * @param key The localStorage key
 * @returns A function telling whether a flag is set, and one setting it
 */
export function useStoredFlags(key: string) {
  const raw = useSyncExternalStore(subscribe, () => localStorage.getItem(key));
  const isSet = useMemo(() => {
    const names = parseNames(raw);
    return (name: string) => names.includes(name);
  }, [raw]);
  const set = useCallback(
    (name: string, value: boolean) => setFlag(key, name, value),
    [key],
  );

  return [isSet, set] as const;
}

/**
 * Same as useStoredFlags for a single flag. Re-renders only when that flag
 * changes, not when another flag of the set does.
 */
export function useStoredFlag(key: string, name: string) {
  const value = useSyncExternalStore(subscribe, () =>
    parseNames(localStorage.getItem(key)).includes(name),
  );
  const set = useCallback(
    (newValue: boolean) => setFlag(key, name, newValue),
    [key, name],
  );

  return [value, set] as const;
}
