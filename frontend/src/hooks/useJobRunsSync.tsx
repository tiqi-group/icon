import { Dispatch, useEffect } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { JobRun } from "../types/JobRun";
import { Action, JobRunUpdate } from "../contexts/JobRunsContext";
import { SerializedObject } from "../types/SerializedObject";

interface NewJobRunEvent {
  job_run: JobRun;
}

/**
 * Synchronizes the latest job run per job with the backend scheduler.
 *
 * - Fetches the initial map via `scheduler.get_job_runs`.
 * - Listens for `job_run.new` and `job_run.update` events.
 * - Cleans up socket listeners on unmount.
 */
export function useJobRunsSync(dispatch: Dispatch<Action>) {
  useEffect(() => {
    runMethod("scheduler.get_job_runs", [], {}, (ack) => {
      dispatch({
        type: "SET_JOB_RUNS",
        payload: deserialize(ack as SerializedObject),
      });
    });

    const handleNew = (data: NewJobRunEvent) =>
      dispatch({ type: "ADD_JOB_RUN", payload: data.job_run });
    const handleUpdate = (data: JobRunUpdate) =>
      dispatch({ type: "UPDATE_JOB_RUN", payload: data });

    socket.on("job_run.new", handleNew);
    socket.on("job_run.update", handleUpdate);

    return () => {
      socket.off("job_run.new", handleNew);
      socket.off("job_run.update", handleUpdate);
    };
  }, [dispatch]);
}
