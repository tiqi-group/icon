import { Typography } from "@mui/material";
import { Job } from "../../types/Job";

const count = (value: number | undefined): string =>
  value !== undefined && Number.isSafeInteger(value) && value >= 0
    ? value.toLocaleString()
    : "—";

/** Persisted submission settings, not acquisition progress. */
export function JobPlanSummary({ job }: { job: Job }) {
  return (
    <Typography variant="body2" sx={{ my: 0.5 }}>
      Planned: {count(job.number_of_shots)}{" "}
      {job.number_of_shots === 1 ? "shot" : "shots"}/point · {count(job.repetitions)}{" "}
      {job.repetitions === 1 ? "repetition" : "repetitions"}
    </Typography>
  );
}
