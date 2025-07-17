import { runMethod } from "../socket";

export const cancelJob = (jobId: number, callback?: (ack: unknown) => void) => {
  runMethod("scheduler.cancel_job", [], { job_id: jobId }, callback);
};
