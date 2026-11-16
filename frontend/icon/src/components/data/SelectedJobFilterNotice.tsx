import { Alert } from "@mui/material";
import { useJobInfo } from "../../hooks/useJobInfo";
import { jobToListItem } from "../../contexts/JobsContext";
import { matchesDataFilters } from "../../utils/dataFilters";
import type { DataFilters } from "../../utils/dataFilters";

export function SelectedJobFilterNotice({
  jobId,
  filters,
}: {
  jobId: number;
  filters: DataFilters;
}) {
  const job = useJobInfo(String(jobId));
  return job && job.id === jobId && !matchesDataFilters(jobToListItem(job), filters) ? (
    <Alert severity="info" sx={{ m: 1 }}>
      Job {jobId} is outside the active filters. Its detail view remains pinned.
    </Alert>
  ) : null;
}
