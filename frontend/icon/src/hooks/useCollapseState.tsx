import { useCallback, useSyncExternalStore } from "react";

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

const storageKeyOf = (key: string) => `collapseState:${key}`;

const toggleName = (storageKey: string, name: string) => {
  const names = parseNames(localStorage.getItem(storageKey));
  const next = names.includes(name)
    ? names.filter((n) => n !== name)
    : [...names, name];
  localStorage.setItem(storageKey, JSON.stringify(next));
  listeners.forEach((listener) => listener());
};

/**
 * Hook to manage which of a set of named sections are collapsed, stored in
 * localStorage. Only the sections toggled away from the default are stored.
 *
 * @param key Identifies the set of sections
 * @param defaultCollapsed Whether the sections start collapsed
 * @returns A function telling whether a section is collapsed, and one toggling it
 */
export function useCollapseState(key: string, defaultCollapsed = false) {
  const storageKey = storageKeyOf(key);
  const toggled = parseNames(
    useSyncExternalStore(subscribe, () => localStorage.getItem(storageKey)),
  );

  const isCollapsed = (name: string) => toggled.includes(name) !== defaultCollapsed;
  const toggle = useCallback(
    (name: string) => toggleName(storageKey, name),
    [storageKey],
  );

  return [isCollapsed, toggle] as const;
}

/**
 * Same as useCollapseState for a single section. Re-renders only when that
 * section is toggled, not when another section of the set is.
 */
export function useSectionCollapsed(
  key: string,
  name: string,
  defaultCollapsed = false,
) {
  const storageKey = storageKeyOf(key);
  const collapsed = useSyncExternalStore(
    subscribe,
    () =>
      parseNames(localStorage.getItem(storageKey)).includes(name) !== defaultCollapsed,
  );
  const toggle = useCallback(() => toggleName(storageKey, name), [storageKey, name]);

  return [collapsed, toggle] as const;
}
