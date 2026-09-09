import React, { useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  CircularProgress,
  FormControlLabel,
  List,
  ListItem,
  ListItemButton,
  ListItemText,
  ListSubheader,
  Switch,
  Tooltip,
} from "@mui/material";
import SsidChartIcon from "@mui/icons-material/SsidChart";
import { JobsContext } from "../contexts/JobsContext";
import { JobView } from "../components/JobView";
import { useNavigate, useSearchParams } from "react-router";
import { JobListItem } from "../types/JobListItem";
import { JobStatus } from "../types/enums";
import { JobStatusIndicator } from "../components/JobStatusIndicator";
import { openJobWindow, openVisualizerWindow } from "../utils/windowUtils";
import { getExperimentNameFromExperimentId } from "../utils/experimentUtils";

type GroupName = "In Progress" | "Queued" | "Finished";

export function DataPage() {
  const { jobs, loading, hasMore, loadMore } = useContext(JobsContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const selectedJobId = searchParams.get("jobId");

  const groupedJobs = useMemo(() => {
    const group: Record<GroupName, JobListItem[]> = {
      "In Progress": [],
      Queued: [],
      Finished: [],
    };

    for (const job of Object.values(jobs)) {
      if (job.status == JobStatus.PROCESSED) group["Finished"].push(job);
      else if (job.status == JobStatus.PROCESSING) group["In Progress"].push(job);
      else if (job.status == JobStatus.SUBMITTED) group["Queued"].push(job);
    }

    for (const status of Object.keys(group)) {
      group[status as GroupName].sort((a, b) => b.id - a.id);
    }

    return group;
  }, [jobs]);

  const [alwaysShowLatest, setAlwaysShowLatest] = useState(false);

  const latestJobId = useMemo(() => {
    let latest: number | null = null;
    for (const id of Object.keys(jobs)) {
      const numericId = Number(id);
      if (latest === null || numericId > latest) latest = numericId;
    }
    return latest;
  }, [jobs]);

  useEffect(() => {
    if (alwaysShowLatest && latestJobId !== null) {
      setSearchParams({ jobId: String(latestJobId) });
    }
  }, [alwaysShowLatest, latestJobId]);

  const handleSelectJob = (jobId: number) => {
    setSearchParams({ jobId: String(jobId) });
  };

  // Infinite scroll: load the next page once the sentinel below the finished
  // jobs comes into view. The observer is re-created whenever the list grows, so
  // that a page too short to fill the column immediately triggers the next one.
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLLIElement>(null);
  const finishedCount = groupedJobs.Finished.length;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { root: scrollRef.current, rootMargin: "200px" },
    );
    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [hasMore, loadMore, finishedCount]);

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div
        ref={scrollRef}
        style={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          overflowY: "auto",
          borderRight: "1px solid var(--mui-palette-divider)",
        }}
      >
        <Tooltip title="Switch to newest job as it's created">
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={alwaysShowLatest}
                onChange={(_, v) => setAlwaysShowLatest(v)}
              />
            }
            label="Latest"
            sx={{ mx: 1, my: 0.5 }}
          />
        </Tooltip>
        <List dense disablePadding>
          {(Object.entries(groupedJobs) as [GroupName, JobListItem[]][]).map(
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
                      second: "2-digit",
                    }).format(new Date(job.created));

                    return (
                      <ListItemButton
                        key={job.id}
                        selected={String(job.id) === selectedJobId}
                        onClick={() => handleSelectJob(job.id)}
                        onDoubleClick={() => openJobWindow(job.id, job.experiment_id)}
                      >
                        <JobStatusIndicator
                          status={job.run_status ?? undefined}
                          log={null}
                        />
                        <ListItemText
                          primary={`${getExperimentNameFromExperimentId(job.experiment_id)} (${
                            job.num_scan_parameters === 0
                              ? "continuous scan"
                              : `${job.num_scan_parameters}d scan`
                          })`}
                          secondary={formattedTime}
                        />
                      </ListItemButton>
                    );
                  })}
                  {status === "Finished" && hasMore && (
                    <ListItem
                      ref={sentinelRef}
                      sx={{ justifyContent: "center", py: 1 }}
                    >
                      <CircularProgress size={20} />
                    </ListItem>
                  )}
                </React.Fragment>
              ),
          )}
        </List>
        {loading && <div style={{ padding: 16 }}>Loading jobs...</div>}
      </div>

      <div style={{ flexGrow: 1, height: "100%", overflow: "auto" }}>
        {selectedJobId ? (
          <div style={{ width: "100%" }}>
            <Tooltip title="Show the pulse sequence of this job in the sequence visualizer">
              <Button
                size="small"
                startIcon={<SsidChartIcon />}
                sx={{ m: 1 }}
                onClick={() => {
                  if (localStorage.getItem("openVisualizerInNewWindow") !== "false") {
                    openVisualizerWindow(selectedJobId);
                  } else {
                    navigate(`/sequence?jobId=${selectedJobId}`);
                  }
                }}
              >
                Open in visualizer
              </Button>
            </Tooltip>
            {loading ? (
              <div style={{ padding: 16 }}>Loading...</div>
            ) : (
              <JobView jobId={selectedJobId} showFitPanel />
            )}
          </div>
        ) : (
          <div style={{ padding: 16 }}>Select a job to view its details</div>
        )}
      </div>
    </div>
  );
}
