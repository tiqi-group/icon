import React, { useContext, useMemo } from "react";
import { List, ListItemButton, ListItemText, ListSubheader } from "@mui/material";
import { JobsContext } from "../contexts/JobsContext";
import { JobView } from "../components/JobView";
import { useSearchParams } from "react-router";
import { Job } from "../types/Job";
import { JobStatus } from "../types/enums";
import { getExperimentNameFromExperimentId } from "./experiments";

export function DataPage() {
  const jobs = useContext(JobsContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedJobId = searchParams.get("jobId");

  const groupedJobs = useMemo(() => {
    const group = {
      "In Progress": [] as Job[],
      Queued: [] as Job[],
      Finished: [] as Job[],
    };

    for (const job of Object.values(jobs)) {
      if (job.status == JobStatus.PROCESSED) group["Finished"].push(job);
      else if (job.status == JobStatus.PROCESSING) group["In Progress"].push(job);
      else if (job.status == JobStatus.SUBMITTED) group["Queued"].push(job);
    }

    for (const status of Object.keys(group)) {
      group[status as "Queued" | "Finished" | "In Progress"].sort(
        (a, b) => b.id - a.id,
      );
    }

    return group;
  }, [jobs]);

  const layoutReady = useMemo(() => {
    return Object.values(groupedJobs).some((list) => list.length > 0);
  }, [groupedJobs]);

  const handleSelectJob = (jobId: number) => {
    setSearchParams({ jobId: String(jobId) });
  };

  return (
    <div style={{ display: "flex", height: "100%" }}>
      <div
        style={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          overflowY: "auto",
          borderRight: "1px solid var(--mui-palette-divider)",
        }}
      >
        <List dense disablePadding>
          {(Object.entries(groupedJobs) as [JobStatus, Job[]][]).map(
            ([status, jobList]) =>
              jobList.length > 0 && (
                <React.Fragment key={status}>
                  <ListSubheader
                    sx={{
                      position: "sticky",
                      borderBottom: "1px solid var(--mui-palette-divider)",
                    }}
                  >
                    {status}
                  </ListSubheader>
                  {jobList.map((job) => {
                    const formattedTime = new Intl.DateTimeFormat("ch", {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                      hour: "2-digit",
                      minute: "2-digit",
                    }).format(new Date(job.created));

                    return (
                      <ListItemButton
                        key={job.id}
                        selected={String(job.id) === selectedJobId}
                        onClick={() => handleSelectJob(job.id)}
                        onDoubleClick={() => {
                          const base = window.location.origin;
                          const url = `${base}/data/${job.id}`;
                          window.open(
                            url,
                            "_blank",
                            "toolbar=no,location=no,status=no,menubar=no,scrollbars=yes,resizable=yes,width=600,height=500,left=100,top=100",
                          );
                        }}
                      >
                        <ListItemText
                          primary={`${getExperimentNameFromExperimentId(job.experiment_source.experiment_id)} (${
                            job.scan_parameters.length === 0
                              ? "continuous scan"
                              : `${job.scan_parameters.length}d scan`
                          })`}
                          secondary={formattedTime}
                        />
                      </ListItemButton>
                    );
                  })}
                </React.Fragment>
              ),
          )}
        </List>
      </div>

      <div style={{ width: "100%" }}>
        {selectedJobId ? (
          <div style={{ width: "100%" }}>
            {layoutReady ? (
              <JobView jobId={selectedJobId} />
            ) : (
              <div style={{ padding: 16 }}>Loading...</div>
            )}
          </div>
        ) : (
          <div style={{ padding: 16 }}>Select a job to view its details</div>
        )}
      </div>
    </div>
  );
}
