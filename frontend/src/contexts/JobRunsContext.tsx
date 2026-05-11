import { createContext } from "react";
import { JobRun } from "../types/JobRun";

export interface JobRunUpdate {
  run_id: number;
  job_id: number;
  updated_properties: Record<string, string>;
}

export type JobRunsByJobId = Record<number, JobRun>;

export type Action =
  | { type: "SET_JOB_RUNS"; payload: JobRunsByJobId }
  | { type: "ADD_JOB_RUN"; payload: JobRun }
  | { type: "UPDATE_JOB_RUN"; payload: JobRunUpdate };

export const reducer = (state: JobRunsByJobId, action: Action): JobRunsByJobId => {
  switch (action.type) {
    case "SET_JOB_RUNS":
      return { ...state, ...action.payload };
    case "ADD_JOB_RUN":
      return { ...state, [action.payload.job_id]: action.payload };
    case "UPDATE_JOB_RUN": {
      const run = state[action.payload.job_id];
      if (!run) return state;

      return {
        ...state,
        [action.payload.job_id]: { ...run, ...action.payload.updated_properties },
      };
    }
    default:
      return state;
  }
};

export const JobRunsContext = createContext<JobRunsByJobId>({});
