import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { Job } from "../types/Job";
import { JobListItem } from "../types/JobListItem";
import {
  JobRunUpdate,
  JobUpdate,
  JobsState,
  ScheduledJobs,
  jobToListItem,
  reducer,
} from "../contexts/JobsContext";
import { JobRun } from "../types/JobRun";
import { SerializedObject } from "../types/SerializedObject";

interface NewDataEvent {
  job: Job;
}

interface NewJobRunEvent {
  job_run: JobRun;
}

/** Number of finished jobs fetched per page. */
export const JOB_PAGE_SIZE = 100;

const toJobMap = (items: JobListItem[]): ScheduledJobs =>
  Object.fromEntries(items.map((item) => [item.id, item]));

/**
 * React hook that synchronizes the job state with the backend scheduler.
 *
 * Jobs are loaded in two parts:
 * - `scheduler.get_active_jobs` returns every queued and running job.
 * - `scheduler.get_job_list` returns finished jobs one page at a time, newest
 *   first, paginated with a cursor on the job ID.
 *
 * @returns The loaded jobs plus the loading flags and the `loadMore` callback
 *   that fetches the next page of finished jobs.
 */
export function useJobsSync(): JobsState {
  const [jobs, dispatch] = useReducer(reducer, {});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  /** Lowest finished job ID loaded so far; the cursor for the next page. */
  const cursor = useRef<number | null>(null);
  const requestInFlight = useRef(false);

  const fetchPage = useCallback((beforeId: number | null, advanceCursor = true) => {
    if (requestInFlight.current) return;
    requestInFlight.current = true;

    const kwargs: Record<string, unknown> = { limit: JOB_PAGE_SIZE };
    if (beforeId !== null) kwargs.before_id = beforeId;

    runMethod("scheduler.get_job_list", [], kwargs, (ack) => {
      requestInFlight.current = false;
      setLoadingMore(false);
      setLoading(false);

      const page = deserialize(ack as SerializedObject);
      if (page instanceof Error || !Array.isArray(page)) {
        console.error("Failed to load jobs:", page);
        setHasMore(false);
        return;
      }

      const items = page as JobListItem[];
      if (advanceCursor) {
        // A short page indicates tail
        setHasMore(items.length === JOB_PAGE_SIZE);
      }
      if (items.length === 0) return;

      if (advanceCursor) cursor.current = items[items.length - 1].id;
      dispatch({ type: "SET_JOBS", payload: toJobMap(items) });
    });
  }, []);

  const loadMore = useCallback(() => {
    if (requestInFlight.current || !hasMore) return;
    setLoadingMore(true);
    fetchPage(cursor.current);
  }, [fetchPage, hasMore]);

  const loadJobs = useCallback(() => {
    runMethod("scheduler.get_active_jobs", [], {}, (ack) => {
      const active = deserialize(ack as SerializedObject);
      if (active instanceof Error || !Array.isArray(active)) {
        console.error("Failed to load active jobs:", active);
        return;
      }
      dispatch({ type: "SET_JOBS", payload: toJobMap(active as JobListItem[]) });
    });

    fetchPage(null, cursor.current === null);
  }, [fetchPage]);

  useEffect(() => {
    // While disconnected, the "connect" handler below does the initial load instead.
    if (socket.connected) loadJobs();

    const onNewJob = (data: NewDataEvent) =>
      dispatch({ type: "ADD_JOB", payload: jobToListItem(data.job) });
    const onJobUpdate = (data: JobUpdate) =>
      dispatch({ type: "UPDATE_JOB", payload: data });
    const onNewJobRun = (data: NewJobRunEvent) =>
      dispatch({ type: "SET_JOB_RUN", payload: data.job_run });
    const onJobRunUpdate = (data: JobRunUpdate) =>
      dispatch({ type: "UPDATE_JOB_RUN", payload: data });
    // Reset response pending state on disconnect
    const onDisconnect = () => {
      requestInFlight.current = false;
      setLoadingMore(false);
    };

    socket.on("connect", loadJobs);
    socket.on("disconnect", onDisconnect);
    socket.on("job.new", onNewJob);
    socket.on("job.update", onJobUpdate);
    socket.on("job_run.new", onNewJobRun);
    socket.on("job_run.update", onJobRunUpdate);

    return () => {
      socket.off("connect", loadJobs);
      socket.off("disconnect", onDisconnect);
      socket.off("job.new", onNewJob);
      socket.off("job.update", onJobUpdate);
      socket.off("job_run.new", onNewJobRun);
      socket.off("job_run.update", onJobRunUpdate);
    };
  }, [loadJobs]);

  return { jobs, loading, loadingMore, hasMore, loadMore };
}
