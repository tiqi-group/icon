export interface ViewerBounds {
  xMin: number | null;
  xMax: number | null;
  yMin: number | null;
  yMax: number | null;
}
export const AUTO_BOUNDS: ViewerBounds = {
  xMin: null,
  xMax: null,
  yMin: null,
  yMax: null,
};
export interface ViewerAxis {
  type?: string;
  data?: unknown[];
  min?: unknown;
  max?: unknown;
}

export function categoryCoordinate(item: unknown): number | null {
  const value = item && typeof item === "object" && "value" in item ? item.value : item;
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string" || !value.trim()) return null;
  const numeric = Number(value);
  if (Number.isFinite(numeric)) return numeric;
  // Histogram labels describe integer-count bins, e.g. 10–14.
  const bin = value.match(/^(-?\d+(?:\.\d+)?)[–—]/);
  if (bin) return Number(bin[1]);
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

export function axisInputType(axis?: ViewerAxis): "number" | "datetime-local" | null {
  if (!axis) return null;
  // ECharts defaults a Cartesian axis without an explicit type to "value".
  if (!axis.type) return "number";
  if (axis.type === "time") return "datetime-local";
  if (axis.type === "value") return "number";
  if (axis.type !== "category" || !axis.data?.length) return null;
  if (axis.data.some((item) => categoryCoordinate(item) === null)) return null;
  return typeof axis.data[0] === "string" && /^\d{4}-\d{2}-\d{2}T/.test(axis.data[0])
    ? "datetime-local"
    : "number";
}

/** Convert operator coordinates to category indices, never treat values as indices. */
export function axisBounds(
  axis: ViewerAxis | undefined,
  min: number | null,
  max: number | null,
) {
  if (
    (min !== null && !Number.isFinite(min)) ||
    (max !== null && !Number.isFinite(max))
  )
    throw new Error("Enter finite axis limits.");
  if (min !== null && max !== null && min >= max)
    throw new Error("Each minimum must be less than its maximum.");
  if (axis?.type !== "category")
    return { min: min ?? axis?.min ?? null, max: max ?? axis?.max ?? null };
  if (min === null && max === null)
    return { min: axis.min ?? null, max: axis.max ?? null };
  const values = (axis.data ?? []).map(categoryCoordinate);
  if (!values.length || values.some((value) => value === null))
    throw new Error("This axis has no numeric coordinates available.");
  const low = min === null ? 0 : values.findIndex((value) => value! >= min);
  const high =
    max === null
      ? values.length - 1
      : values.reduce<number>(
          (last, value, index) => (value! <= max ? index : last),
          -1,
        );
  if (low < 0 || high < low)
    throw new Error("No axis samples fall within these limits.");
  return { min: low, max: high };
}

/** Live category changes can invalidate previously accepted bounds without user input. */
export function resolveAxisBounds(
  axis: ViewerAxis | undefined,
  min: number | null,
  max: number | null,
):
  | { valid: true; bounds: ReturnType<typeof axisBounds> }
  | { valid: false; error: string } {
  try {
    return { valid: true, bounds: axisBounds(axis, min, max) };
  } catch (error) {
    return {
      valid: false,
      error: error instanceof Error ? error.message : String(error),
    };
  }
}
