import { useEffect, useState } from "react";
import { runMethod, socket } from "../socket";
import { Job } from "../types/Job";
import { SerializedObject } from "../types/SerializedObject";
import { deserialize } from "../utils/deserializer";
import { JobUpdate } from "../contexts/JobsContext";

export const useJobInfo = (jobId: string | undefined) => {
  const [jobInfo, setJobInfo] = useState<Job | null>(null);

  useEffect(() => {
    if (jobId === undefined) return;

    const fetchJob = () => {
      runMethod("scheduler.get_job_by_id", [], { job_id: jobId }, (ack) => {
        const deserialized = deserialize(ack as SerializedObject) as Job | Error;
        if (deserialized instanceof Error) {
          console.info("Failed to fetch job:", deserialized);
          return;
        }
        setJobInfo(deserialized);
      });
    };

    fetchJob();

    const handleJobUpdate = (data: JobUpdate) => {
      if (data.job_id !== Number.parseInt(jobId)) return;

      setJobInfo((prev) => {
        if (!prev) {
          fetchJob();
          return null;
        }
        return {
          ...prev,
          ...data.updated_properties,
        };
      });
    };

    socket.on("job.update", handleJobUpdate);
    return () => {
      socket.off("job.update", handleJobUpdate);
    };
  }, [jobId]);

  return jobInfo;
};
