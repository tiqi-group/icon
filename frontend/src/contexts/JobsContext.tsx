import { createContext } from "react";
import { Job } from "../types/Job";

export interface JobUpdate {
  job_id: string;
  updated_properties: Record<string, string>;
}

export type ScheduledJobs = Record<string, Job>;

export type Action =
  | { type: "SET_JOBS"; payload: ScheduledJobs }
  | { type: "ADD_JOB"; payload: Job }
  | { type: "UPDATE_JOB"; payload: JobUpdate };

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
    default:
      return state;
  }
};

export const JobsContext = createContext<ScheduledJobs>({});
