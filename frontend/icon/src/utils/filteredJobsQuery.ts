import { jobToListItem, reducer } from "../contexts/JobsContext";
import type { Action, ScheduledJobs } from "../contexts/JobsContext";
import type { Job } from "../types/Job";
import type { JobListItem } from "../types/JobListItem";
import { dataFilterArguments, matchesDataFilters } from "./dataFilters";
import type { DataFilters } from "./dataFilters";

export interface FilteredJobsSnapshot {
  jobs: ScheduledJobs;
  loading: boolean;
  loadingMore: boolean;
  hasMore: boolean;
  error: string | null;
}
export const emptyFilteredJobs: FilteredJobsSnapshot = {
  jobs: {},
  loading: true,
  loadingMore: false,
  hasMore: false,
  error: null,
};
type Request = (
  method: string,
  args: Record<string, unknown>,
  done: (value: unknown) => void,
) => void;
const PAGE_SIZE = 100;

/** A page-local query: independent cursors and generations leave the shared feed alone. */
export class FilteredJobsQuery {
  state: FilteredJobsSnapshot = emptyFilteredJobs;
  private generation = 0;
  private disposed = false;
  private pending = 0;
  private cursor: number | null = null;
  constructor(
    private filters: DataFilters,
    private request: Request,
    private changed: (state: FilteredJobsSnapshot) => void,
  ) {}

  private publish(change: Partial<FilteredJobsSnapshot>) {
    this.state = { ...this.state, ...change };
    this.changed(this.state);
  }
  private current(generation: number) {
    return !this.disposed && generation === this.generation;
  }
  private merge(items: JobListItem[]) {
    const fetched = Object.fromEntries(
      items
        .filter((job) => matchesDataFilters(job, this.filters))
        .map((job) => [job.id, job]),
    );
    // Live changes received during a fetch take precedence over its older snapshot.
    this.publish({ jobs: { ...fetched, ...this.state.jobs } });
  }
  private requestPage(
    method: "scheduler.get_active_jobs" | "scheduler.get_job_list",
    before: number | null,
    done: (value: unknown) => void,
  ) {
    if (this.filters.experiments?.length === 0) {
      done([]);
      return;
    }
    this.request(
      method,
      {
        ...dataFilterArguments(this.filters),
        limit: PAGE_SIZE,
        ...(before !== null && { before_id: before }),
      },
      done,
    );
  }
  refresh = () => {
    if (this.disposed) return;
    const generation = ++this.generation;
    this.cursor = null;
    this.pending = 2;
    this.publish({ ...emptyFilteredJobs });
    this.page(generation, null);
    this.requestPage("scheduler.get_active_jobs", null, (value) => {
      if (!this.current(generation)) return;
      if (Array.isArray(value)) this.merge(value as JobListItem[]);
      else
        this.publish({
          error:
            value instanceof Error
              ? value.message
              : "Could not load active matching jobs.",
        });
      this.pending--;
      this.publish({ loading: this.pending > 0 });
    });
  };
  private page(generation: number, before: number | null) {
    this.requestPage("scheduler.get_job_list", before, (value) => {
      if (!this.current(generation)) return;
      if (Array.isArray(value)) {
        const items = value as JobListItem[];
        this.merge(items);
        if (items.length) this.cursor = items[items.length - 1].id;
        this.publish({ hasMore: items.length === PAGE_SIZE });
      } else
        this.publish({
          error:
            value instanceof Error ? value.message : "Could not load matching jobs.",
          hasMore: false,
        });
      if (before === null) this.pending--;
      this.publish({ loading: this.pending > 0, loadingMore: false });
    });
  }
  loadMore = () => {
    if (
      this.disposed ||
      this.state.loading ||
      this.state.loadingMore ||
      !this.state.hasMore ||
      this.state.error
    )
      return;
    this.publish({ loadingMore: true });
    this.page(this.generation, this.cursor);
  };
  update(action: Action) {
    if (this.disposed || this.filters.experiments?.length === 0) return;
    if (action.type === "ADD_JOB" && !matchesDataFilters(action.payload, this.filters))
      return;
    if (action.type === "UPDATE_JOB" && !this.state.jobs[action.payload.job_id]) {
      const generation = this.generation;
      this.request(
        "scheduler.get_job_by_id",
        { job_id: action.payload.job_id },
        (value) => {
          if (!this.current(generation) || !value || value instanceof Error) return;
          const job = jobToListItem(value as Job);
          if (matchesDataFilters(job, this.filters)) this.merge([job]);
        },
      );
      return;
    }
    const jobs = reducer(this.state.jobs, action);
    this.publish({
      jobs: Object.fromEntries(
        Object.entries(jobs).filter(([, job]) => matchesDataFilters(job, this.filters)),
      ),
    });
  }
  disconnect = () => {
    this.generation++;
    this.publish({
      loading: false,
      loadingMore: false,
      error: "Connection lost. Matching jobs will refresh when reconnected.",
    });
  };
  dispose() {
    this.disposed = true;
    this.generation++;
  }
}
