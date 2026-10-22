import { useEffect, useState } from "react";
import { runMethod, socket } from "../../socket";
import { deserialize } from "../../utils/deserializer";
import type { SerializedObject } from "../../types/SerializedObject";
import type { Job } from "../../types/Job";
import type { JobRun } from "../../types/JobRun";

export function usePlotViewerJob(jobId: string, connected: boolean) {
  const [job, setJob] = useState<Job | null>(null);
  const [run, setRun] = useState<JobRun | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    let generation = 0;
    let runId: number | undefined;
    setRun(null);
    if (!connected) return;
    const refresh = () => {
      const request = ++generation;
      const accept = () => current && request === generation;
      runMethod("scheduler.get_job_by_id", [], { job_id: Number(jobId) }, (ack) => {
        if (!accept()) return;
        const value = deserialize(ack as SerializedObject) as Job | Error | null;
        if (!value || value instanceof Error || value.id !== Number(jobId)) {
          setError("This job could not be loaded.");
          return;
        }
        setError(null);
        setJob(value);
      });
      runMethod("scheduler.get_job_run_by_id", [], { job_id: Number(jobId) }, (ack) => {
        if (!accept()) return;
        const value = deserialize(ack as SerializedObject) as JobRun | Error | null;
        if (!value || value instanceof Error || value.job_id !== Number(jobId)) return;
        runId = value.id;
        setRun(value);
      });
    };
    const jobUpdate = (event: { job_id: number }) => {
      if (event.job_id === Number(jobId)) refresh();
    };
    const runUpdate = (event: { run_id: number }) => {
      if (runId === undefined || event.run_id === runId) refresh();
    };
    socket.on("job.update", jobUpdate);
    socket.on("job_run.update", runUpdate);
    refresh();
    return () => {
      current = false;
      socket.off("job.update", jobUpdate);
      socket.off("job_run.update", runUpdate);
    };
  }, [jobId, connected]);
  return { job, run, error };
}
