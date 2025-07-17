import { Tooltip } from "@mui/material";
import { JobRunStatus } from "../types/enums";

const statusColorMap: Record<JobRunStatus, string> = {
  [JobRunStatus.PENDING]: "grey",
  [JobRunStatus.CANCELLED]: "grey",
  [JobRunStatus.DONE]: "grey",
  [JobRunStatus.PROCESSING]: "green",
  [JobRunStatus.FAILED]: "red",
};

export const JobStatusIndicator = ({
  status,
  log,
}: {
  status: JobRunStatus | undefined;
  log: string | null | undefined;
}) => {
  return (
    <Tooltip title={log ? log : status}>
      <span
        style={{
          display: "flex",
          alignItems: "center",
          width: 15,
          height: 15,
          borderRadius: "50%",
          backgroundColor: status ? statusColorMap[status] : "grey",
          marginRight: 8,
        }}
      />
    </Tooltip>
  );
};
