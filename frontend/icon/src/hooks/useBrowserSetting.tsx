import { useState, useEffect, useCallback } from "react";

/**
 * Hook to manage a browser setting stored in localStorage with reactive updates.
 *
 * @param key The localStorage key
 * @param defaultValue Default value when nothing is stored
 */
export function useBrowserSetting<T extends string | boolean | number>(
  key: string,
  defaultValue: T,
) {
  // Read from localStorage (or fallback to default)
  const readValue = (): T => {
    const item = localStorage.getItem(key);
    if (item === null) return defaultValue;
    if (typeof defaultValue === "boolean") return (item === "true") as T;
    if (typeof defaultValue === "number") {
      const num = Number(item);
      return (Number.isFinite(num) ? num : defaultValue) as T;
    }
    return item as T;
  };

  const [value, setValue] = useState<T>(readValue);

  // Keep value updated if localStorage changes
  useEffect(() => {
    const handler = (e: StorageEvent) => {
      if (e.key === key) {
        setValue(readValue());
      }
    };
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, [key]);

  // Save to localStorage when value changes
  const setAndStoreValue = useCallback(
    (newValue: T) => {
      setValue(newValue);
      localStorage.setItem(key, String(newValue));
    },
    [key],
  );

  return [value, setAndStoreValue] as const;
}
