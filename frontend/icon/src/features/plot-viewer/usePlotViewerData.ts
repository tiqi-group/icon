import { useEffect, useRef, useState } from "react";
import { runMethod, socket } from "../../socket";
import type { SerializedObject } from "../../types/SerializedObject";
import { deserialize } from "../../utils/deserializer";
import {
  applyPlotViewerUpdate,
  bufferPlotViewerUpdate,
  createPlotViewerBuffer,
  EMPTY_PLOT_VIEWER_DATA,
  LIVE_POINT_LIMIT,
  normalizePlotViewerLimit,
  retainPlotViewerData,
  replayPlotViewerBuffer,
  validatePlotViewerSnapshot,
} from "./plotViewerData";
import type {
  PlotViewerBuffer,
  PlotViewerData,
  PlotViewerUpdate,
} from "./plotViewerData";

const SNAPSHOT_TIMEOUT_MS = 20_000;
const SNAPSHOT_RETRY_INTERVAL_MS = 5_000;
const asError = (value: unknown) =>
  value instanceof Error ? value : new Error(String(value));

/** Viewer-only bounded snapshots, with immutable live updates and reconnect replay. */
export function usePlotViewerData(
  jobId?: string,
  requestedLivePointLimit = LIVE_POINT_LIMIT,
) {
  const livePointLimit = normalizePlotViewerLimit(requestedLivePointLimit);
  const retained = useRef<{
    jobId?: string;
    data: PlotViewerData;
    hasSnapshot: boolean;
  }>({ data: EMPTY_PLOT_VIEWER_DATA, hasSnapshot: false });
  const [experimentData, setExperimentData] =
    useState<PlotViewerData>(EMPTY_PLOT_VIEWER_DATA);
  const [experimentDataError, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(Boolean(jobId));
  const [connected, setConnected] = useState(socket.connected);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let active = true;
    let generation = 0;
    const sameJob = retained.current.jobId === jobId;
    let current = sameJob
      ? retainPlotViewerData(retained.current.data, livePointLimit)
      : EMPTY_PLOT_VIEWER_DATA;
    let buffer: PlotViewerBuffer | null = null;
    let hasSnapshot = sameJob && retained.current.hasSnapshot;
    const publishCurrent = () => {
      retained.current = { jobId, data: current, hasSnapshot };
      setExperimentData(current);
    };
    let snapshotFailed = false;
    let lastSnapshotStarted = 0;
    let retryTimeout: ReturnType<typeof setTimeout> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    publishCurrent();
    setError(null);
    setLoading(Boolean(jobId) && !hasSnapshot);
    setRefreshing(false);
    setConnected(socket.connected);

    if (!jobId) return;
    const numericJobId = Number(jobId);
    if (!Number.isSafeInteger(numericJobId) || numericJobId < 1) {
      setError(new Error("Invalid job ID"));
      setLoading(false);
      return;
    }

    const clearTimeoutIfNeeded = () => {
      if (timeout !== undefined) clearTimeout(timeout);
      timeout = undefined;
    };
    const clearRetry = () => {
      if (retryTimeout !== undefined) clearTimeout(retryTimeout);
      retryTimeout = undefined;
    };
    const scheduleSnapshotRetry = () => {
      if (!snapshotFailed || buffer || retryTimeout !== undefined || !socket.connected)
        return;
      // Live bursts coalesce into one request, at most once per five seconds.
      retryTimeout = setTimeout(
        () => {
          retryTimeout = undefined;
          if (active && socket.connected && snapshotFailed && !buffer) fetchSnapshot();
        },
        Math.max(0, SNAPSHOT_RETRY_INTERVAL_MS - (Date.now() - lastSnapshotStarted)),
      );
    };
    const acceptUpdate = (update: PlotViewerUpdate) => {
      if (!active) return;
      try {
        const next = applyPlotViewerUpdate(current, update, livePointLimit);
        const nextBuffer = buffer
          ? bufferPlotViewerUpdate(buffer, update, livePointLimit)
          : null;
        current = next;
        buffer = nextBuffer;
        publishCurrent();
        if (update.type === "point" || update.type === "metadata")
          scheduleSnapshotRetry();
      } catch (error) {
        setError(asError(error));
      }
    };

    const fetchSnapshot = () => {
      const requestGeneration = ++generation;
      clearTimeoutIfNeeded();
      clearRetry();
      snapshotFailed = false;
      lastSnapshotStarted = Date.now();
      buffer = createPlotViewerBuffer(current.realtime_scan);
      setLoading(!hasSnapshot);
      setRefreshing(hasSnapshot);
      setError(null);
      const finish = () => {
        clearTimeoutIfNeeded();
        buffer = null;
        setLoading(false);
        setRefreshing(false);
      };
      timeout = setTimeout(() => {
        if (!active || generation !== requestGeneration) return;
        ++generation;
        snapshotFailed = true;
        setError(
          new Error("Experiment snapshot request timed out; live data is retained."),
        );
        finish();
      }, SNAPSHOT_TIMEOUT_MS);
      runMethod(
        "data.get_experiment_data_by_job_id",
        [],
        {
          job_id: numericJobId,
          max_transfer_bytes: 4_000_000,
          include_hardware_instructions: false,
          include_all_shots: false,
        },
        (ack) => {
          if (!active || generation !== requestGeneration) return;
          try {
            const serialized = ack as SerializedObject;
            const value: unknown =
              serialized.type === "str"
                ? JSON.parse(serialized.value)
                : deserialize(serialized);
            if (value instanceof Error) throw value;
            const snapshot = validatePlotViewerSnapshot(value, livePointLimit);
            current = buffer
              ? replayPlotViewerBuffer(snapshot, buffer, livePointLimit)
              : snapshot;
            hasSnapshot = true;
            publishCurrent();
            setError(null);
          } catch (error) {
            snapshotFailed = true;
            setError(asError(error));
          }
          finish();
        },
      );
    };

    const handleConnect = () => {
      if (!active) return;
      setConnected(true);
      fetchSnapshot();
    };
    const handleDisconnect = () => {
      if (!active) return;
      ++generation;
      clearTimeoutIfNeeded();
      clearRetry();
      buffer = null;
      setConnected(false);
      setLoading(false);
      setRefreshing(false);
    };
    const handleConnectError = (error: Error) => {
      handleDisconnect();
      if (active) setError(asError(error));
    };
    type Point = Extract<PlotViewerUpdate, { type: "point" }>["value"];
    type Metadata = Extract<PlotViewerUpdate, { type: "metadata" }>["value"];
    type Parameters = Extract<PlotViewerUpdate, { type: "parameters" }>["value"];
    type Fit = Extract<PlotViewerUpdate, { type: "fit" }>["value"];
    const handlePoint = (value: Point) => acceptUpdate({ type: "point", value });
    const handleMetadata = (value: Metadata) =>
      acceptUpdate({ type: "metadata", value });
    const handleParameters = (value: Parameters) =>
      acceptUpdate({ type: "parameters", value });
    const handleFit = (value: Fit) => acceptUpdate({ type: "fit", value });
    const pointEvent = `experiment_${jobId}`;
    const metadataEvent = `experiment_${jobId}_metadata`;
    const parametersEvent = `experiment_params_${jobId}`;
    const fitEvent = `experiment_fit_${jobId}`;

    socket.on(pointEvent, handlePoint);
    socket.on(metadataEvent, handleMetadata);
    socket.on(parametersEvent, handleParameters);
    socket.on(fitEvent, handleFit);
    socket.on("connect", handleConnect);
    socket.on("disconnect", handleDisconnect);
    socket.on("connect_error", handleConnectError);
    if (socket.connected) fetchSnapshot();

    return () => {
      active = false;
      ++generation;
      clearTimeoutIfNeeded();
      clearRetry();
      socket.off(pointEvent, handlePoint);
      socket.off(metadataEvent, handleMetadata);
      socket.off(parametersEvent, handleParameters);
      socket.off(fitEvent, handleFit);
      socket.off("connect", handleConnect);
      socket.off("disconnect", handleDisconnect);
      socket.off("connect_error", handleConnectError);
    };
  }, [jobId, livePointLimit]);

  return { experimentData, experimentDataError, loading, connected, refreshing };
}
