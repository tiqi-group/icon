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

    runMethod("scheduler.get_job_run_by_id", [], { job_id: jobId }, (ack) => {
      setJobRunInfo(deserialize(ack as SerializedObject) as JobRun);
    });

    const handleJobRunUpdate = (data: JobRunUpdate) => {
      setJobRunInfo((prevJobRunInfo) => {
        if (!prevJobRunInfo || data.run_id !== prevJobRunInfo?.id)
          return prevJobRunInfo;

        const updatedJobRun = {
          ...prevJobRunInfo,
          ...data.updated_properties,
        };

        return updatedJobRun as JobRun;
      });
    };

    socket.on("job_run.update", handleJobRunUpdate);
    return () => {
      socket.off("job_run.update", handleJobRunUpdate);
    };
  }, [jobId]);

  return jobRunInfo;
};
