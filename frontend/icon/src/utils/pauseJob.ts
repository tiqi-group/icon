import { runMethod } from "../socket";

export const pauseJob = (jobId: number, callback?: (ack: unknown) => void) => {
  runMethod("scheduler.pause_job", [], { job_id: jobId }, callback);
};
