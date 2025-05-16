import React, { useReducer, createContext, useContext } from "react";
import { Job } from "../types/Job";

// Define State Type
interface SchedulerState {
  scheduledJobs: Job[];
}

// Define Actions
type Action =
  | { type: "SET_JOBS"; payload: Job[] }
  | { type: "ADD_JOB"; payload: Job }
  | { type: "REMOVE_JOB"; id: string };

// Reducer Function
const reducer = (state: SchedulerState, action: Action): SchedulerState => {
  switch (action.type) {
    case "SET_JOBS":
      return { ...state, scheduledJobs: action.payload };
    case "ADD_JOB":
      return { ...state, scheduledJobs: [...state.scheduledJobs, action.payload] };
    case "REMOVE_JOB":
      return {
        ...state,
        scheduledJobs: state.scheduledJobs.filter(
          (job) => job.id !== parseInt(action.id),
        ),
      };
    default:
      return state;
  }
};

// Create Context
const SchedulerContext = createContext<{
  state: SchedulerState;
  dispatch: React.Dispatch<Action>;
}>({
  state: { scheduledJobs: [] },
  dispatch: () => {},
});

// Provider Component
export const SchedulerProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [state, dispatch] = useReducer(reducer, { scheduledJobs: [] });

  return (
    <SchedulerContext.Provider value={{ state, dispatch }}>
      {children}
    </SchedulerContext.Provider>
  );
};

// Custom Hook for Access
export const useSchedulerContext = () => {
  const context = useContext(SchedulerContext);
  if (!context) {
    throw new Error("useSchedulerContext must be used within a SchedulerProvider");
  }
  return context;
};
