import { useCallback, useEffect, useState } from "react";
import {
  parseExperimentFavorites,
  toggleExperimentFavorites,
} from "../utils/experimentFavorites";

const STORAGE_KEY = "experimentFavorites";
const readFavorites = () => {
  try {
    return parseExperimentFavorites(localStorage.getItem(STORAGE_KEY));
  } catch {
    return [];
  }
};

export function useExperimentFavorites() {
  const [favorites, setFavorites] = useState<string[]>(readFavorites);
  useEffect(() => {
    const sync = (event: StorageEvent) => {
      if (event.key === STORAGE_KEY || event.key === null)
        setFavorites(readFavorites());
    };
    window.addEventListener("storage", sync);
    return () => window.removeEventListener("storage", sync);
  }, []);
  const toggle = useCallback(
    (ids: string[]) => {
      let stored = favorites;
      try {
        const raw = localStorage.getItem(STORAGE_KEY);
        if (raw !== null) stored = parseExperimentFavorites(raw);
      } catch {
        /* Keep the in-session preference. */
      }
      const next = toggleExperimentFavorites(stored, ids);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        /* Storage may be unavailable. */
      }
      setFavorites(next);
    },
    [favorites],
  );
  return [favorites, toggle] as const;
}
