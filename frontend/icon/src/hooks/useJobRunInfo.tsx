import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";
import { JobRun } from "../types/JobRun";

export interface JobRunUpdate {
  run_id: number;
  updated_properties: Record<string, string>;
}

export const useJobRunInfo = (jobId: string | undefined) => {
  const [jobRunInfo, setJobRunInfo] = useState<JobRun | null>(null);

  useEffect(() => {
    if (jobId === undefined) return;

    const fetchJobRun = () => {
      runMethod("scheduler.get_job_run_by_id", [], { job_id: jobId }, (ack) => {
        const deserialized = deserialize(ack as SerializedObject);
        if (deserialized instanceof Error) {
          console.info("Failed to fetch job run:", deserialized);
          return;
        }
        setJobRunInfo(deserialized as JobRun);
      });
    };

    fetchJobRun();

    const handleJobRunUpdate = (data: JobRunUpdate) => {
      setJobRunInfo((prev) => {
        if (!prev || data.run_id !== prev.id) {
          fetchJobRun();
          return prev;
        }

        return {
          ...prev,
          ...data.updated_properties,
        } as JobRun;
      });
    };

    socket.on("job_run.update", handleJobRunUpdate);
    return () => {
      socket.off("job_run.update", handleJobRunUpdate);
    };
  }, [jobId]);

  return jobRunInfo;
};
