import { createContext } from "react";
import { Job } from "../types/Job";
import { JobListItem } from "../types/JobListItem";
import { JobRun } from "../types/JobRun";
import { JobRunStatus } from "../types/enums";

export interface JobUpdate {
  job_id: number;
  updated_properties: Record<string, string>;
}

export type ScheduledJobs = Record<number, JobListItem>;

export interface JobRunUpdate {
  run_id: number;
  updated_properties: Record<string, string>;
}

export type Action =
  | { type: "SET_JOBS"; payload: ScheduledJobs }
  | { type: "ADD_JOB"; payload: JobListItem }
  | { type: "UPDATE_JOB"; payload: JobUpdate }
  | { type: "SET_JOB_RUN"; payload: JobRun }
  | { type: "UPDATE_JOB_RUN"; payload: JobRunUpdate };

export const jobToListItem = (job: Job): JobListItem => ({
  id: job.id,
  created: job.created,
  status: job.status,
  experiment_id: job.experiment_source.experiment_id,
  num_scan_parameters: job.scan_parameters.length,
  // A newly submitted job has no run yet; `job_run.new` fills these in.
  run_id: null,
  run_status: null,
});

// Reducer Function
export const reducer = (state: ScheduledJobs, action: Action): ScheduledJobs => {
  switch (action.type) {
    case "SET_JOBS":
      return { ...state, ...action.payload };
    case "ADD_JOB":
      return { ...state, [action.payload.id]: action.payload };
    case "UPDATE_JOB": {
      const job = state[action.payload.job_id];
      // job not found, no update
      if (!job) return state;

      return {
        ...state,
        [action.payload.job_id]: { ...job, ...action.payload.updated_properties },
      };
    }
    case "SET_JOB_RUN": {
      const job = state[action.payload.job_id];
      if (!job) return state;

      return {
        ...state,
        [action.payload.job_id]: {
          ...job,
          run_id: action.payload.id,
          run_status: action.payload.status,
        },
      };
    }
    case "UPDATE_JOB_RUN": {
      const status = action.payload.updated_properties.status as
        JobRunStatus | undefined;
      if (status === undefined) return state;

      const entry = Object.values(state).find(
        (job) => job.run_id === action.payload.run_id,
      );
      if (!entry) return state;

      return { ...state, [entry.id]: { ...entry, run_status: status } };
    }
    default:
      return state;
  }
};

export interface JobsState {
  /** All jobs loaded so far, keyed by ID. */
  jobs: ScheduledJobs;
  /** True while the first page is still in flight. */
  loading: boolean;
  /** True while an additional page is being fetched. */
  loadingMore: boolean;
  /** False once the oldest job has been loaded. */
  hasMore: boolean;
  /** Load the next page of finished jobs. */
  loadMore: () => void;
}

export const JobsContext = createContext<JobsState>({
  jobs: {},
  loading: true,
  loadingMore: false,
  hasMore: false,
  loadMore: () => {},
});
