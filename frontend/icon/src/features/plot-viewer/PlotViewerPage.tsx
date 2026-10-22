import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router";
import { ReactRouterAppProvider } from "@toolpad/core/react-router";
import {
  Alert,
  Box,
  Button,
  Card,
  Chip,
  CircularProgress,
  FormControlLabel,
  Switch,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import ResultChannelPlot from "../../components/ResultChannelPlot";
import HistogramPlot from "../../components/jobView/HistogramPlot";
import FitPanel from "../../components/jobView/FitPanel";
import type { ExperimentData } from "../../types/ExperimentData";
import { JobRunStatus } from "../../types/enums";
import {
  averageRepeatedPlot,
  hasFittablePoints,
  hasNumericScanAxis,
  observedScanParameters,
  projectPlotData,
  selectPlot,
} from "./plotSelection";
import { usePlotViewerData } from "./usePlotViewerData";
import { usePlotViewerJob } from "./usePlotViewerJob";
import { ViewerChart, ViewerInteractionContext } from "./ViewerChart";
import { ViewerFullscreenButton } from "./ViewerFullscreenButton";
import { ViewerWindowSize } from "./ViewerWindowSize";
import { ViewerHeatmap } from "./ViewerHeatmap";
import { RepetitionSeriesContext, ViewerTraceChart } from "./ViewerTraceChart";
import { repetitionSeries } from "./repetitionSeries";
import { ViewerPlotIdentityContext, viewerPlotIdentity } from "./viewerPlotIdentity";
import { readViewerWindowSize, rememberViewerWindowSize } from "./viewerPreferences";

function PlotViewer({
  jobId,
  kind,
  plotIndex,
  deviceId,
}: {
  jobId: string;
  kind?: string;
  plotIndex?: string;
  deviceId: string | null;
}) {
  const [windowSize, setWindowSize] = useState(readViewerWindowSize);
  const [showRepetitions, setShowRepetitions] = useState(false);
  const { experimentData, experimentDataError, loading, connected, refreshing } =
    usePlotViewerData(jobId, Math.max(2000, windowSize));
  const {
    job,
    run,
    experimentName,
    error: jobError,
  } = usePlotViewerJob(jobId, connected);
  const [heldData, setHeldData] = useState<ExperimentData | null>(null);
  const [resetToken, setResetToken] = useState(0);
  const [clickedX, setClickedX] = useState<number | null>(null);
  const source = heldData ?? experimentData;
  const selection = useMemo(
    () => selectPlot(source, deviceId, kind, plotIndex),
    [source, deviceId, kind, plotIndex],
  );
  const currentFits = experimentData.device_data.find(
    (device) => device.device_id === selection?.device.device_id,
  )?.fits;
  const rawPlotData = useMemo(
    () =>
      selection
        ? projectPlotData(
            source,
            { ...selection.device, fits: currentFits ?? selection.device.fits },
            selection.plot.channel_names,
          )
        : null,
    [source, selection, currentFits],
  );
  const plotData = useMemo(
    () =>
      rawPlotData
        ? averageRepeatedPlot(
            rawPlotData,
            job?.scan_parameters ?? [],
            job?.repetitions ?? 1,
          )
        : null,
    [rawPlotData, job],
  );
  const is2D = job?.scan_parameters.length === 2;
  const chartStyle = {
    height: `max(420px, calc(100dvh - ${270 + (heldData ? 64 : 0) + (is2D && showRepetitions ? 56 : 0)}px))`,
    width: "100%",
  };
  const individualSeries = useMemo(
    () =>
      showRepetitions && rawPlotData && job?.scan_parameters.length === 1
        ? repetitionSeries(rawPlotData, job.scan_parameters[0], windowSize)
        : [],
    [showRepetitions, rawPlotData, job, windowSize],
  );
  const parameters = useMemo(
    () =>
      plotData && job ? observedScanParameters(plotData, job.scan_parameters) : [],
    [plotData, job],
  );
  const holdView = useCallback(
    () => setHeldData((previous) => previous ?? experimentData),
    [experimentData],
  );
  const follow = () => {
    setHeldData(null);
    setResetToken((value) => value + 1);
  };
  const interaction = useMemo(() => ({ holdView, resetToken }), [holdView, resetToken]);
  const points = Object.keys(
    Object.values(plotData?.device_data[0]?.readouts.result_channels ?? {})[0] ?? {},
  ).length;
  const visiblePoints = is2D ? points : Math.min(points, windowSize);
  const changeWindowSize = (value: number) => {
    setWindowSize(value);
    rememberViewerWindowSize(value);
    setResetToken((token) => token + 1);
  };
  const isTrace = kind === "readout";
  const supported =
    !isTrace ||
    !job ||
    job.scan_parameters.length === 0 ||
    job.scan_parameters.length === 2 ||
    (job.scan_parameters.length === 1 &&
      (job.scan_parameters[0].realtime || (plotData && hasNumericScanAxis(plotData))));
  const canFit =
    isTrace &&
    connected &&
    !refreshing &&
    run?.status === JobRunStatus.DONE &&
    job?.scan_parameters.length === 1 &&
    !job.scan_parameters[0].realtime &&
    plotData &&
    hasFittablePoints(plotData);

  const identity = useMemo(
    () =>
      viewerPlotIdentity(
        (selection?.plot.name ?? "Plot") +
          (kind === "histogram" ? " (latest point)" : ""),
        jobId,
        selection?.device.device_id ?? deviceId ?? "",
        experimentName,
        run?.scheduled_time,
      ),
    [
      kind,
      selection?.plot.name,
      selection?.device.device_id,
      jobId,
      deviceId,
      experimentName,
      run?.scheduled_time,
    ],
  );
  const hasChart = Boolean(plotData && selection && supported);

  useEffect(() => {
    document.title = `${selection?.plot.name ?? "Plot"} · Job ${jobId}`;
  }, [selection?.plot.name, jobId]);

  return (
    <Box
      component="main"
      sx={{ p: { xs: 1.5, sm: 3 }, minHeight: "100vh", bgcolor: "background.default" }}
    >
      <Stack spacing={2}>
        <Stack
          direction="row"
          alignItems="center"
          justifyContent={hasChart ? "flex-end" : "space-between"}
          gap={2}
          flexWrap="wrap"
        >
          {!hasChart && (
            <Box>
              <Typography variant="h5" component="h1">
                {selection?.plot.name ?? "Plot viewer"}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                Job {jobId}
                {selection ? ` · ${selection.device.device_id}` : ""}
              </Typography>
            </Box>
          )}
          <Stack direction="row" gap={1} alignItems="center" flexWrap="wrap">
            <ViewerFullscreenButton />
            <Button
              component={Link}
              to={`/data/${jobId}`}
              variant="outlined"
              size="small"
            >
              All job plots
            </Button>
          </Stack>
        </Stack>
        <Stack direction="row" alignItems="center" gap={1.5} flexWrap="wrap">
          <ToggleButtonGroup
            exclusive
            value={heldData ? "hold" : "follow"}
            onChange={(_, value) => {
              if (value === "hold") holdView();
              else if (value === "follow") follow();
            }}
            size="small"
            aria-label="View updates"
            disabled={loading || !selection}
          >
            <ToggleButton value="follow">Follow live</ToggleButton>
            <ToggleButton value="hold">Hold view</ToggleButton>
          </ToggleButtonGroup>
          {isTrace && !is2D && (
            <ViewerWindowSize value={windowSize} onChange={changeWindowSize} />
          )}
          {isTrace && (job?.repetitions ?? 1) > 1 && (
            <FormControlLabel
              control={
                <Switch
                  checked={showRepetitions}
                  onChange={(_, checked) => setShowRepetitions(checked)}
                />
              }
              label="Show individual repetitions"
            />
          )}
          <Chip
            size="small"
            label={
              !connected
                ? "Disconnected"
                : refreshing
                  ? "Refreshing"
                  : (run?.status ?? "Loading job")
            }
            color={
              !connected
                ? "warning"
                : run?.status === JobRunStatus.PROCESSING
                  ? "success"
                  : "default"
            }
          />
          <Typography
            variant="body2"
            color="text.secondary"
            data-testid="received-points"
          >
            {experimentData.total_data_points.toLocaleString()} points acquired
          </Typography>
          {isTrace && (
            <Typography variant="body2" color="text.secondary">
              {visiblePoints.toLocaleString()}{" "}
              {is2D
                ? "loaded samples"
                : (job?.repetitions ?? 1) > 1
                  ? "scan positions in window"
                  : "points in window"}
            </Typography>
          )}
        </Stack>
        {!connected && (
          <Alert severity="warning">
            Connection lost. Showing the last received data; this viewer will refresh
            when the connection returns.
          </Alert>
        )}
        {heldData && (
          <Alert severity="info">
            View held. Incoming data continues in the background. Choose Follow live to
            return to the latest data.
          </Alert>
        )}
        {(experimentDataError || jobError) && (
          <Alert severity="error">{String(experimentDataError || jobError)}</Alert>
        )}
        {loading && (
          <Box sx={{ py: 6, textAlign: "center" }}>
            <CircularProgress aria-label="Loading plot" />
          </Box>
        )}
        {!loading && !selection && !experimentDataError && (
          <Alert severity="info">
            This plot is not available for this job and device. It may appear when
            acquisition starts. Use All job plots to choose another plot.
          </Alert>
        )}
        {!supported && (
          <Alert severity="info">
            This viewer supports numeric one-dimensional traces, time traces,
            two-dimensional scans, and histograms. Use All job plots for this scan.
          </Alert>
        )}
        {plotData && selection && supported && (
          <Card variant="outlined" sx={{ p: { xs: 0.5, sm: 1.5 } }}>
            <ViewerPlotIdentityContext.Provider value={identity}>
              <ViewerInteractionContext.Provider value={interaction}>
                {isTrace && is2D && rawPlotData && job ? (
                  <ViewerHeatmap
                    experimentData={rawPlotData}
                    scanParameters={job.scan_parameters}
                    channelNames={selection.plot.channel_names}
                    loading={loading}
                    chartStyle={chartStyle}
                    showRepetitions={showRepetitions}
                  />
                ) : isTrace ? (
                  <RepetitionSeriesContext.Provider value={individualSeries}>
                    <ResultChannelPlot
                      experimentData={plotData}
                      channelNames={selection.plot.channel_names}
                      title=""
                      subtitle=""
                      loading={loading}
                      repetitions={1}
                      showRepetitions={false}
                      scanParameters={parameters}
                      windowSize={windowSize}
                      fits={plotData.device_data[0].fits}
                      onChartClick={canFit ? setClickedX : undefined}
                      ChartComponent={ViewerTraceChart}
                      chartStyle={chartStyle}
                    />
                  </RepetitionSeriesContext.Provider>
                ) : (
                  <HistogramPlot
                    experimentData={plotData}
                    channelNames={selection.plot.channel_names}
                    title=""
                    subtitle="Latest acquired point"
                    loading={loading}
                    ChartComponent={ViewerChart}
                    chartStyle={chartStyle}
                  />
                )}
              </ViewerInteractionContext.Provider>
            </ViewerPlotIdentityContext.Provider>
          </Card>
        )}
        {isTrace && (job?.repetitions ?? 1) > 1 && (
          <Typography variant="caption" color="text.secondary">
            {is2D
              ? "Values are averaged at each coordinate unless an individual repetition is selected."
              : showRepetitions
                ? "Mean and individual repetitions are shown. Window size counts scan positions."
                : "Repetitions are averaged. Window size counts scan positions."}
          </Typography>
        )}
        {isTrace &&
          !is2D &&
          Object.keys(Object.values(source.scan_parameters)[0] ?? {}).length <
            source.total_data_points && (
            <Typography variant="caption" color="text.secondary">
              Showing the latest {visiblePoints.toLocaleString()} loaded points. The
              job's saved data is unchanged.
              {points < windowSize &&
                ` Requested ${windowSize.toLocaleString()}; ${points.toLocaleString()} are available${heldData ? " in this held view. Choose Follow live to load more history" : " within the loaded history"}.`}
            </Typography>
          )}
        {canFit && plotData && (
          <Box>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Set the fit range below; zoom and window size do not set the fit range.
              Successful fits are saved with the job.
            </Typography>
            <FitPanel
              jobId={jobId}
              experimentData={plotData}
              clickedX={clickedX}
              scanParameters={job?.scan_parameters}
              allowParameterUpdates={false}
            />
          </Box>
        )}
        {isTrace && !is2D && selection && !canFit && (
          <Typography variant="caption" color="text.secondary">
            Fitting is available for completed one-dimensional numeric scans, with at
            least three points, while connected.
          </Typography>
        )}
      </Stack>
    </Box>
  );
}

export function PlotViewerPage() {
  const { jobId, kind, plotIndex } = useParams();
  const [search] = useSearchParams();
  const deviceId = search.get("device");
  return (
    <ReactRouterAppProvider>
      {jobId && /^\d+$/.test(jobId) ? (
        <PlotViewer
          key={`${jobId}/${kind}/${plotIndex}/${deviceId}`}
          jobId={jobId}
          kind={kind}
          plotIndex={plotIndex}
          deviceId={deviceId}
        />
      ) : (
        <Alert severity="error">Invalid job identifier.</Alert>
      )}
    </ReactRouterAppProvider>
  );
}
