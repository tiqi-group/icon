import { Fragment, useContext, useEffect, useMemo, useRef } from "react";
import {
  Alert,
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
import { useBrowserSetting } from "../hooks/useBrowserSetting";
import { useNavigate, useSearchParams } from "react-router";
import { JobListItem } from "../types/JobListItem";
import { JobStatus } from "../types/enums";
import { JobStatusIndicator } from "../components/JobStatusIndicator";
import { openJobWindow, openVisualizerWindow } from "../utils/windowUtils";
import { getExperimentNameFromExperimentId } from "../utils/experimentUtils";
import {
  latestDataJobId,
  resolveDataJobId,
  withDataJobSelection,
} from "../utils/dataJobSelection";
import { DataFilters } from "../components/data/DataFilters";
import { SelectedJobFilterNotice } from "../components/data/SelectedJobFilterNotice";
import { useFilteredDataJobs } from "../hooks/useFilteredDataJobs";
import {
  dataFilterError,
  hasDataFilters,
  readDataFilters,
  withDataFilters,
} from "../utils/dataFilters";
import { emptyFilteredJobs } from "../utils/filteredJobsQuery";
import "../components/data/filters.css";

type GroupName = "In Progress" | "Queued" | "Finished";

export function DataPage() {
  const sharedJobs = useContext(JobsContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const filters = readDataFilters(searchParams);
  const filtering = hasDataFilters(filters);
  const filterError = dataFilterError(filters);
  const filteredJobs = useFilteredDataJobs(filters, filtering && !filterError);
  const { jobs, loading, loadingMore, hasMore, loadMore } = filterError
    ? { ...emptyFilteredJobs, loading: false, loadMore: () => {} }
    : filtering
      ? filteredJobs
      : sharedJobs;
  const navigate = useNavigate();
  const jobSelection = searchParams.get("jobId");
  // Match upstream: follow by default on a tab's first unqualified visit, and
  // remember the toggle per tab as following puts a numeric job ID in the URL.
  const [alwaysShowLatest, setAlwaysShowLatest] = useBrowserSetting<boolean>(
    "alwaysShowLatest",
    jobSelection === null,
    sessionStorage,
  );
  useEffect(() => {
    setAlwaysShowLatest(alwaysShowLatest);
  }, [alwaysShowLatest, setAlwaysShowLatest]);

  const latestJobId = useMemo(() => latestDataJobId(jobs), [jobs]);
  const selectedJobId = alwaysShowLatest ? latestJobId : resolveDataJobId(jobSelection);

  useEffect(() => {
    if (!alwaysShowLatest || loading) return;
    // Preserve the filter query and avoid adding every live job to Back history.
    // Clear a stale selection when the filtered feed has no matches.
    const next = withDataJobSelection(searchParams, latestJobId);
    if (next.toString() !== searchParams.toString()) {
      setSearchParams(next, { replace: true });
    }
  }, [alwaysShowLatest, latestJobId, loading, searchParams, setSearchParams]);

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

  const handleSelectJob = (jobId: number) => {
    if (jobId !== latestJobId) setAlwaysShowLatest(false);
    const next = withDataJobSelection(searchParams, jobId);
    if (next.toString() !== searchParams.toString()) setSearchParams(next);
  };

  // Infinite scroll: load the next page once the sentinel below the finished
  // jobs comes into view. The observer is re-created whenever the list grows, so
  // that a page too short to fill the column immediately triggers the next one.
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLLIElement>(null);
  const finishedCount = groupedJobs.Finished.length;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading || loadingMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) loadMore();
      },
      { root: scrollRef.current, rootMargin: "200px" },
    );
    observer.observe(sentinel);

    return () => observer.disconnect();
  }, [hasMore, loadMore, finishedCount, loading, loadingMore]);

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div
        className="icon-data-sidebar"
        style={{
          flexShrink: 0,
          width: "fit-content",
          height: "100%",
          borderRight: "1px solid var(--mui-palette-divider)",
        }}
      >
        <DataFilters
          filters={filters}
          onApply={(filters) => {
            const next = withDataFilters(searchParams, filters);
            if (next.size === 0) {
              setSearchParams(next, { state: { clearRememberedSearch: true } });
            } else {
              setSearchParams(next);
            }
          }}
        />
        <Tooltip
          title={
            filtering
              ? "Follow the newest job matching these filters. Selecting an older job turns this off."
              : "Switch to newest job as it's created. Selecting an older job turns this off."
          }
        >
          <FormControlLabel
            control={
              <Switch
                size="small"
                checked={alwaysShowLatest}
                onChange={(_, checked) => setAlwaysShowLatest(checked)}
              />
            }
            label={filtering ? "Latest matching" : "Latest"}
            sx={{ mx: 1, my: 0.5 }}
          />
        </Tooltip>
        {filterError && <Alert severity="error">{filterError}</Alert>}
        {filtering && filteredJobs.error && !filterError && (
          <Alert
            severity="error"
            action={
              <Button size="small" onClick={filteredJobs.retry}>
                Retry
              </Button>
            }
          >
            {filteredJobs.error}
          </Alert>
        )}
        <div ref={scrollRef} className="icon-data-job-scroll">
          <List dense disablePadding>
            {(Object.entries(groupedJobs) as [GroupName, JobListItem[]][]).map(
              ([status, jobList]) =>
                jobList.length > 0 && (
                  <Fragment key={status}>
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
                          selected={job.id === selectedJobId}
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
                  </Fragment>
                ),
            )}
            {hasMore && (
              <ListItem
                ref={sentinelRef}
                sx={{ justifyContent: "center", py: 1, minHeight: 36 }}
              >
                {loadingMore && <CircularProgress size={20} disableShrink />}
              </ListItem>
            )}
          </List>
          {loading && <div style={{ padding: 16 }}>Loading jobs...</div>}
          {filtering &&
            !loading &&
            !filterError &&
            !filteredJobs.error &&
            Object.keys(jobs).length === 0 && (
              <div className="icon-data-query-message">
                No jobs match these filters.
              </div>
            )}
        </div>
      </div>

      <div style={{ flexGrow: 1, height: "100%", overflow: "auto" }}>
        {selectedJobId !== null ? (
          <div style={{ width: "100%" }}>
            {filtering && !filterError && !alwaysShowLatest && (
              <SelectedJobFilterNotice
                key={`filter-notice-${selectedJobId}`}
                jobId={selectedJobId}
                filters={filters}
              />
            )}
            <Tooltip title="Show the pulse sequence of this job in the sequence visualizer">
              <Button
                size="small"
                startIcon={<SsidChartIcon />}
                sx={{ m: 1 }}
                onClick={() => {
                  if (localStorage.getItem("openVisualizerInNewWindow") !== "false") {
                    openVisualizerWindow(String(selectedJobId));
                  } else {
                    navigate(`/sequence?jobId=${selectedJobId}`);
                  }
                }}
              >
                Open in visualizer
              </Button>
            </Tooltip>
            {loading && alwaysShowLatest ? (
              <div style={{ padding: 16 }}>Loading...</div>
            ) : (
              <JobView key={selectedJobId} jobId={String(selectedJobId)} showFitPanel />
            )}
          </div>
        ) : (
          <div style={{ padding: 16 }}>
            {alwaysShowLatest
              ? loading
                ? "Loading..."
                : filtering
                  ? "Waiting for a matching job"
                  : "Waiting for a job"
              : "Select a job to view its details"}
          </div>
        )}
      </div>
    </div>
  );
}
