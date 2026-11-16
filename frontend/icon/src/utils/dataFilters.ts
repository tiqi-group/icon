import type { JobListItem } from "../types/JobListItem";

export interface DataFilters {
  experiments: string[] | null;
  from: string;
  to: string;
  job: string;
}
export const emptyDataFilters: DataFilters = {
  experiments: null,
  from: "",
  to: "",
  job: "",
};
const dateAndJobKeys = ["from", "to", "job"] as const;

export function readDataFilters(params: URLSearchParams): DataFilters {
  const experiments = params.getAll("experiment");
  return {
    // Missing means All; a present but empty parameter means None.
    experiments: experiments.length ? [...new Set(experiments.filter(Boolean))] : null,
    from: params.get("from") ?? "",
    to: params.get("to") ?? "",
    job: params.get("job") ?? "",
  };
}
export const hasDataFilters = (filters: DataFilters) =>
  filters.experiments !== null || dateAndJobKeys.some((key) => filters[key] !== "");

export function dataFilterError(filters: DataFilters): string | null {
  for (const value of [filters.from, filters.to]) {
    if (!value) continue;
    const parsed = new Date(value + "T00:00:00Z");
    if (
      !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
      value < "0001-01-01" ||
      value > "9999-12-30" ||
      !Number.isFinite(parsed.getTime()) ||
      parsed.toISOString().slice(0, 10) !== value
    )
      return "Enter valid calendar dates.";
  }
  if (filters.from && filters.to && filters.from > filters.to)
    return "From date must not be after through date.";
  if (
    filters.job &&
    (!/^\d+$/.test(filters.job) ||
      !Number.isSafeInteger(Number(filters.job)) ||
      Number(filters.job) < 1)
  )
    return "Job ID must be a positive whole number.";
  return null;
}

export function withDataFilters(
  params: URLSearchParams,
  filters: DataFilters,
): URLSearchParams {
  const next = new URLSearchParams(params);
  next.delete("experiment");
  if (filters.experiments !== null) {
    for (const id of filters.experiments.length ? filters.experiments : [""]) {
      next.append("experiment", id);
    }
  }
  for (const key of dateAndJobKeys) {
    if (filters[key]) next.set(key, filters[key]);
    else next.delete(key);
  }
  return next;
}

export function dataFilterArguments(filters: DataFilters): Record<string, unknown> {
  return {
    ...(filters.experiments !== null && { experiment_ids: filters.experiments }),
    ...(filters.from && { created_from: filters.from }),
    ...(filters.to && { created_to: filters.to }),
    ...(filters.job && { job_id: Number(filters.job) }),
  };
}

export function matchesDataFilters(job: JobListItem, filters: DataFilters): boolean {
  // Serialized timestamps carry ICON's configured zone; keep its calendar date.
  const day = job.created.slice(0, 10);
  return (
    (filters.experiments === null || filters.experiments.includes(job.experiment_id)) &&
    (!filters.from || day >= filters.from) &&
    (!filters.to || day <= filters.to) &&
    (!filters.job || job.id === Number(filters.job))
  );
}

export function experimentDataUrl(experiment: string): string {
  return (
    "/data?" +
    withDataFilters(new URLSearchParams(), {
      ...emptyDataFilters,
      experiments: [experiment],
    }).toString()
  );
}
