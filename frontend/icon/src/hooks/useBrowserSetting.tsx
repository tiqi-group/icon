import { useCallback, useSyncExternalStore } from "react";
import { notifyStorageChange, subscribeToStorage } from "../utils/storageSubscription";

type SettingValue = string | boolean | number;

const parseValue = <T extends SettingValue>(raw: string | null, defaultValue: T): T => {
  if (raw === null) return defaultValue;
  try {
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed === typeof defaultValue) return parsed as T;
  } catch {
    // fall through
  }
  return defaultValue;
};

/**
 * Hook to manage a browser setting stored in localStorage with reactive updates.
 *
 * @param key The storage key
 * @param defaultValue Default value when nothing is stored
 * @param storage sessionStorage for a setting of this browser tab only
 */
export function useBrowserSetting<T extends SettingValue>(
  key: string,
  defaultValue: T,
  storage: Storage = localStorage,
) {
  const raw = useSyncExternalStore(subscribeToStorage, () => storage.getItem(key));
  const value = parseValue(raw, defaultValue);

  const setValue = useCallback(
    (newValue: T) => {
      storage.setItem(key, JSON.stringify(newValue));
      notifyStorageChange();
    },
    [key, storage],
  );

  return [value, setValue] as const;
}
