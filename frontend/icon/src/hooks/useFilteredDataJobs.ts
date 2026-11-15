import { useCallback, useEffect, useRef, useState } from "react";
import { runMethod, socket } from "../socket";
import { deserialize } from "../utils/deserializer";
import { jobToListItem } from "../contexts/JobsContext";
import type { JobUpdate, JobRunUpdate } from "../contexts/JobsContext";
import type { Job } from "../types/Job";
import type { JobRun } from "../types/JobRun";
import type { SerializedObject } from "../types/SerializedObject";
import type { DataFilters } from "../utils/dataFilters";
import { emptyFilteredJobs, FilteredJobsQuery } from "../utils/filteredJobsQuery";

export function useFilteredDataJobs(filters: DataFilters, enabled: boolean) {
  const key = JSON.stringify(filters);
  const current = useRef<FilteredJobsQuery | null>(null);
  const [snapshot, setSnapshot] = useState({ key: "", state: emptyFilteredJobs });
  useEffect(() => {
    if (!enabled) return;
    const query = new FilteredJobsQuery(
      JSON.parse(key),
      (method, args, done) => {
        runMethod(method, [], args, (ack) => {
          try {
            done(deserialize(ack as SerializedObject));
          } catch {
            done(new Error("Invalid response while loading matching jobs."));
          }
        });
      },
      (state) => setSnapshot({ key, state }),
    );
    current.current = query;
    const added = ({ job }: { job: Job }) =>
      query.update({ type: "ADD_JOB", payload: jobToListItem(job) });
    const updated = (payload: JobUpdate) =>
      query.update({ type: "UPDATE_JOB", payload });
    const runAdded = ({ job_run }: { job_run: JobRun }) =>
      query.update({ type: "SET_JOB_RUN", payload: job_run });
    const runUpdated = (payload: JobRunUpdate) =>
      query.update({ type: "UPDATE_JOB_RUN", payload });
    socket.on("job.new", added);
    socket.on("job.update", updated);
    socket.on("job_run.new", runAdded);
    socket.on("job_run.update", runUpdated);
    socket.on("connect", query.refresh);
    socket.on("disconnect", query.disconnect);
    if (socket.connected) query.refresh();
    else query.disconnect();
    return () => {
      query.dispose();
      current.current = null;
      socket.off("job.new", added);
      socket.off("job.update", updated);
      socket.off("job_run.new", runAdded);
      socket.off("job_run.update", runUpdated);
      socket.off("connect", query.refresh);
      socket.off("disconnect", query.disconnect);
    };
  }, [key, enabled]);
  const loadMore = useCallback(() => current.current?.loadMore(), []);
  const retry = useCallback(() => current.current?.refresh(), []);
  return {
    ...(snapshot.key === key ? snapshot.state : emptyFilteredJobs),
    loadMore,
    retry,
  };
}
