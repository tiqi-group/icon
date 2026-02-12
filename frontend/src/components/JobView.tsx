import { useEffect, useState } from "react";
import {
  Alert,
  Button,
  Card,
  CardContent,
  Grid,
  Typography,
  IconButton,
  Switch,
  Tooltip,
  Divider,
} from "@mui/material";
import { ExpandLess, ExpandMore } from "@mui/icons-material";
import ResultChannelPlot from "../components/ResultChannelPlot";
import { JobStatusIndicator } from "../components/JobStatusIndicator";
import { ParameterGroupDisplay } from "../components/ParameterGroupDisplay";
import { useExperimentData } from "../hooks/useExperimentData";
import { useJobRunInfo } from "../hooks/useJobRunInfo";
import { useJobInfo } from "../hooks/useJobInfo";
import { runMethod } from "../socket";
import { ExperimentMetadata } from "../types/ExperimentMetadata";
import { SerializedObject } from "../types/SerializedObject";
import { JobStatus } from "../types/enums";
import { deserialize } from "../utils/deserializer";
import { updateJobParams } from "../utils/updateJobParams";
import { cancelJob } from "../utils/cancelJob";
import HistogramPlot from "./jobView/HistogramPlot";

function getPlotTitle(scheduledTime?: string, experimentName?: string): string {
  if (!scheduledTime) return experimentName || "";
  const baseTime = scheduledTime.split("+")[0].replace("T", " ");
  return `${baseTime}_${experimentName || ""}`;
}

export const JobView = ({
  jobId,
  onLoaded,
}: {
  jobId: string | undefined;
  onLoaded?: () => void;
}) => {
  const [experimentMetadata, setExperimentMetadata] =
    useState<ExperimentMetadata | null>(null);

  const jobInfo = useJobInfo(jobId);
  const jobRunInfo = useJobRunInfo(jobId);
  const { experimentData, experimentDataError, loading } = useExperimentData(jobId);
  const is1D = jobInfo?.scan_parameters.length === 1;

  const loadedDataPoints = Object.keys(
    Object.values(experimentData.result_channels)[0] ?? {},
  ).length;
  const isTruncated =
    experimentData.total_data_points > 0 &&
    loadedDataPoints < experimentData.total_data_points;

  const [showRepetitions, setShowRepetitions] = useState<boolean>(() => {
    const v = localStorage.getItem("showRepetitions");
    return v ? JSON.parse(v) : false;
  });

  // States to track whether the plot sections are expanded or collapsed
  const [expandedShotChannels, setExpandedShotChannels] = useState<
    Record<string, boolean>
  >({});
  const [expandedResultChannels, setExpandedResultChannels] = useState<
    Record<string, boolean>
  >({});

  const toggleShotChannel = (name: string) => {
    const newState = {
      ...expandedShotChannels,
      [name]: expandedShotChannels[name] === false,
    };
    setExpandedShotChannels(newState);
    localStorage.setItem(
      `shotChannelsState_${jobInfo?.experiment_source_id}`,
      JSON.stringify(newState),
    );
  };

  const toggleResultChannel = (name: string) => {
    const newState = {
      ...expandedResultChannels,
      [name]: expandedResultChannels[name] === false,
    };
    setExpandedResultChannels(newState);
    localStorage.setItem(
      `resultChannelsState_${jobInfo?.experiment_source_id}`,
      JSON.stringify(newState),
    );
  };

  // Load expanded/collapsed state from localStorage once after jobInfo has loaded
  useEffect(() => {
    if (jobInfo) {
      const storedShotChannelsState = localStorage.getItem(
        `shotChannelsState_${jobInfo.experiment_source_id}`,
      );
      const storedResultChannelsState = localStorage.getItem(
        `resultChannelsState_${jobInfo.experiment_source_id}`,
      );

      if (storedShotChannelsState) {
        setExpandedShotChannels(JSON.parse(storedShotChannelsState));
      }

      if (storedResultChannelsState) {
        setExpandedResultChannels(JSON.parse(storedResultChannelsState));
      }
    }
  }, [jobInfo]);

  useEffect(() => {
    if (jobInfo?.experiment_source.experiment_id)
      runMethod(
        "experiments.get_metadata",
        [jobInfo?.experiment_source.experiment_id],
        {},
        (ack) => {
          setExperimentMetadata(
            deserialize(ack as SerializedObject) as ExperimentMetadata,
          );
        },
      );
  }, [jobInfo]);

  useEffect(() => {
    localStorage.setItem("showRepetitions", JSON.stringify(showRepetitions));
  }, [showRepetitions]);

  useEffect(() => {
    if (!loading && !experimentDataError && onLoaded) {
      onLoaded();
    }
  }, [loading, experimentDataError, onLoaded]);

  return (
    <div style={{ padding: 16 }}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 12, lg: 12 }}>
          <Card>
            <CardContent>
              <div style={{ display: "flex", alignItems: "center" }}>
                <JobStatusIndicator status={jobRunInfo?.status} log={jobRunInfo?.log} />
                <Typography variant="h6">
                  {jobId}
                  {experimentMetadata?.constructor_kwargs.name && (
                    <>
                      {" "}
                      - {experimentMetadata?.constructor_kwargs.name} (
                      {experimentMetadata?.class_name})
                    </>
                  )}
                </Typography>
                {jobInfo?.status !== JobStatus.PROCESSED && (
                  <>
                    <div style={{ flexGrow: 1 }} />
                    <Button
                      variant="contained"
                      color="error"
                      disabled={jobInfo === null}
                      size="small"
                      onClick={() => {
                        if (jobId) cancelJob(Number(jobId));
                      }}
                    >
                      Cancel
                    </Button>
                  </>
                )}
              </div>
              <Typography variant="body2">
                {jobRunInfo?.scheduled_time ? (
                  <>Scheduled: {jobRunInfo.scheduled_time}</>
                ) : (
                  <>Created: {jobInfo?.created}</>
                )}
              </Typography>
              <Typography variant="body1">{jobInfo?.status}</Typography>
              <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <Typography variant="body2">Show repetitions</Typography>
                <Tooltip
                  title={is1D ? "" : "Repetitions can only be shown for 1D scans"}
                  disableHoverListener={is1D}
                >
                  <span>
                    <Switch
                      checked={showRepetitions}
                      onChange={(_, v) => setShowRepetitions(v)}
                      disabled={!is1D}
                    />
                  </span>
                </Tooltip>
              </div>
            </CardContent>
          </Card>
        </Grid>

        {isTruncated && (
          <Grid size={{ xs: 12 }}>
            <Alert severity="info">
              Showing last {loadedDataPoints.toLocaleString()} of{" "}
              {experimentData.total_data_points.toLocaleString()} data points.
            </Alert>
          </Grid>
        )}

        {experimentData?.plot_windows?.shot_channels?.map((win) => (
          <Grid size={{ xs: 12, sm: 12, lg: 4 }} key={`shot-${win.index}`}>
            <Card>
              <CardContent sx={{ padding: 1 }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  {expandedShotChannels[win.name] === false && (
                    <Typography variant="h6">{win.name}</Typography>
                  )}
                  <div style={{ flexGrow: 1 }} />
                  <IconButton
                    title={
                      expandedShotChannels[win.name] === false ? "Expand" : "Collapse"
                    }
                    onClick={() => toggleShotChannel(win.name)}
                  >
                    {expandedShotChannels[win.name] === false ? (
                      <ExpandMore />
                    ) : (
                      <ExpandLess />
                    )}
                  </IconButton>
                </div>
                {expandedShotChannels[win.name] !== false && (
                  <HistogramPlot
                    experimentData={experimentData}
                    channelNames={win.channel_names}
                    loading={loading}
                    title={win.name}
                    subtitle={getPlotTitle(
                      jobRunInfo?.scheduled_time,
                      experimentMetadata?.constructor_kwargs.name,
                    )}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}

        {experimentData?.plot_windows?.result_channels?.map((win) => (
          <Grid size={{ xs: 12, sm: 12, lg: 6 }} key={`result-${win.index}`}>
            <Card>
              <CardContent sx={{ padding: 1 }}>
                <div style={{ display: "flex", alignItems: "center" }}>
                  {!expandedResultChannels[win.name] && (
                    <Typography variant="h6">{win.name}</Typography>
                  )}
                  <div style={{ flexGrow: 1 }} />
                  <IconButton
                    title={
                      expandedResultChannels[win.name] === false ? "Expand" : "Collapse"
                    }
                    onClick={() => toggleResultChannel(win.name)}
                  >
                    {expandedResultChannels[win.name] === false ? (
                      <ExpandMore />
                    ) : (
                      <ExpandLess />
                    )}
                  </IconButton>
                </div>
                {expandedResultChannels[win.name] !== false && (
                  <ResultChannelPlot
                    experimentData={experimentData}
                    channelNames={win.channel_names}
                    loading={loading}
                    title={win.name}
                    subtitle={getPlotTitle(
                      jobRunInfo?.scheduled_time,
                      experimentMetadata?.constructor_kwargs.name,
                    )}
                    repetitions={jobInfo?.repetitions}
                    showRepetitions={showRepetitions}
                    scanParameters={jobInfo?.scan_parameters}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
        <Grid size={{ xs: 12 }}>
          <Card>
            <CardContent>
              <div style={{ display: "flex", flexDirection: "column" }}>
                <Typography variant="h6">Parameter Values</Typography>
                {Object.entries(experimentMetadata?.parameters || {}).map(
                  ([displayGroup, parameters], index) => (
                    <div key={displayGroup}>
                      <Typography variant="h6">{displayGroup}</Typography>
                      <ParameterGroupDisplay
                        displayGroup={displayGroup}
                        parameters={parameters}
                        values={experimentData.parameters}
                        readOnly={true}
                      />
                      {index <
                        Object.keys(experimentMetadata?.parameters || {}).length -
                          1 && <Divider sx={{ pt: 2 }} />}
                    </div>
                  ),
                )}
                <div style={{ flexGrow: 1, alignContent: "center" }} />
                <Button
                  variant="outlined"
                  color="primary"
                  disabled={jobInfo === null}
                  size="small"
                  onClick={() => {
                    if (jobId) updateJobParams(Number(jobId));
                  }}
                >
                  Update Scan Parameters
                </Button>
              </div>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </div>
  );
};
