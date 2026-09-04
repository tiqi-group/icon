import { runMethod } from "../socket";

export const resumeJob = (jobId: number, callback?: (ack: unknown) => void) => {
  runMethod("scheduler.resume_job", [], { job_id: jobId }, callback);
};
