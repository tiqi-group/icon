import { getExperimentNameFromExperimentId } from "./experimentUtils";

export function parseExperimentFavorites(raw: string | null): string[] {
  try {
    const value: unknown = JSON.parse(raw ?? "[]");
    return Array.isArray(value)
      ? [
          ...new Set(
            value.filter((id): id is string => typeof id === "string" && id.length > 0),
          ),
        ]
      : [];
  } catch {
    return [];
  }
}

export function toggleExperimentFavorites(
  favorites: string[],
  ids: string[],
): string[] {
  const selected = new Set(ids);
  return ids.every((id) => favorites.includes(id))
    ? favorites.filter((id) => !selected.has(id))
    : [...new Set([...favorites, ...ids])];
}

export function availableFavorites(ids: string[], favorites: string[]): string[] {
  const selected = new Set(favorites);
  return ids
    .filter((id) => selected.has(id))
    .sort(
      (a, b) =>
        getExperimentNameFromExperimentId(a).localeCompare(
          getExperimentNameFromExperimentId(b),
        ) || a.localeCompare(b),
    );
}
