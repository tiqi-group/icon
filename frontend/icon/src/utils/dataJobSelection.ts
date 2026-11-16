import type { ScheduledJobs } from "../contexts/JobsContext";

export function resolveDataJobId(selection: string | null): number | null {
  if (selection === null || !/^\d+$/.test(selection)) return null;
  const id = Number(selection);
  return Number.isSafeInteger(id) ? id : null;
}

export function latestDataJobId(jobs: ScheduledJobs): number | null {
  let latest: number | null = null;
  for (const { id } of Object.values(jobs)) {
    if (Number.isSafeInteger(id) && id >= 0 && (latest === null || id > latest)) {
      latest = id;
    }
  }
  return latest;
}

export function withDataJobSelection(
  searchParams: URLSearchParams,
  selection: number | null,
): URLSearchParams {
  const next = new URLSearchParams(searchParams);
  if (selection === null) next.delete("jobId");
  else next.set("jobId", String(selection));
  return next;
}
