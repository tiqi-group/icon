import { Dispatch, useEffect } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { Job } from "../types/Job";
import { JobUpdate, Action } from "../contexts/JobsContext";
import { SerializedObject } from "../types/SerializedObject";

interface NewDataEvent {
  job: Job;
  scheduled_time: string;
}

/**
 * React hook that synchronizes the job state with the backend scheduler.
 *
 * This hook:
 * - Fetches the initial list of scheduled jobs using `scheduler.get_scheduled_jobs`.
 * - Listens for `new_experiment` events and dispatches `ADD_JOB` actions.
 * - Listens for `update_job` events and dispatches `UPDATE_JOB` actions.
 * - Cleans up socket listeners on unmount.
 *
 * @param dispatch - A React dispatch function for the jobs reducer (JobsContext).
 */
export function useJobsSync(dispatch: Dispatch<Action>) {
  useEffect(() => {
    runMethod("scheduler.get_scheduled_jobs", [], {}, (ack) => {
      dispatch({ type: "SET_JOBS", payload: deserialize(ack as SerializedObject) });
    });

    socket.on("job.new", (data: NewDataEvent) =>
      dispatch({ type: "ADD_JOB", payload: data.job }),
    );
    socket.on("job.update", (data: JobUpdate) =>
      dispatch({ type: "UPDATE_JOB", payload: data }),
    );

    return () => {
      socket.off("job.new");
      socket.off("job.update");
    };
  }, [dispatch]);
}
