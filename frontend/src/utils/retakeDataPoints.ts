import { runMethod } from "../socket";

export const retakeDataPoints = (
  jobId: number,
  noDataPoints: number,
  callback?: (ack: unknown) => void,
) => {
  runMethod(
    "scans.retake_data_points",
    [],
    { job_id: jobId, no_data_points: noDataPoints },
    callback,
  );
};
