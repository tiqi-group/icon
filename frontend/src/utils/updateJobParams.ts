import { runMethod } from "../socket";

export const updateJobParams = (
  jobId: number | null = null,
  callback?: (ack: unknown) => void,
) => {
  runMethod("scans.trigger_update_job_params", [], { job_id: jobId }, callback);
};
