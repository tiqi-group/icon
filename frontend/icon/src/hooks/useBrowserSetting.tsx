import { useCallback, useSyncExternalStore } from "react";
import { notifyStorageChange, subscribeToStorage } from "../utils/storageSubscription";

type SettingValue = string | boolean | number | null;

const parseValue = <T extends SettingValue>(raw: string | null, defaultValue: T): T => {
  if (raw === null) return defaultValue;
  try {
    const parsed: unknown = JSON.parse(raw);
    const valid =
      defaultValue === null
        ? parsed !== null && typeof parsed !== "object"
        : typeof parsed === typeof defaultValue;
    if (valid) return parsed as T;
  } catch {
    // fall through
  }
  return defaultValue;
};

/**
 * Hook to manage a browser setting stored in localStorage with reactive updates.
 *
 * @param key The localStorage key
 * @param defaultValue Default value when nothing is stored. Setting null removes the
 *   stored value.
 */
export function useBrowserSetting<T extends SettingValue>(
  key: string,
  defaultValue: T,
) {
  const raw = useSyncExternalStore(subscribeToStorage, () => localStorage.getItem(key));
  const value = parseValue(raw, defaultValue);

  const setValue = useCallback(
    (newValue: T) => {
      if (newValue === null) localStorage.removeItem(key);
      else localStorage.setItem(key, JSON.stringify(newValue));
      notifyStorageChange();
    },
    [key],
  );

  return [value, setValue] as const;
}
