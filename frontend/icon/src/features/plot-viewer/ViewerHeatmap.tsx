import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties } from "react";
import {
  Alert,
  Box,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from "@mui/material";
import * as echarts from "echarts/core";
import type { ECharts } from "echarts/core";
import type { EChartsOption } from "echarts";
import { HeatmapChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { ExperimentData } from "../../types/ExperimentData";
import type { ScanParameter } from "../../types/ScanParameter";
import { CHART_AXIS_NAME, CHART_GRID, CHART_TEXT_STYLE } from "../../utils/chartLayout";
import { formatDateTime } from "../../utils/timeUtils";
import { ViewerChart } from "./ViewerChart";
import { ViewerOverlayCurves } from "./ViewerOverlayCurves";
import type { OverlayHorizontalAxis } from "./overlayCurveData";
import {
  buildHeatmapData,
  heatmapAxisCategories,
  heatmapSeriesData,
} from "./heatmapData";

echarts.use([
  HeatmapChart,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
]);

export interface ViewerHeatmapProps {
  experimentData: ExperimentData;
  scanParameters: ScanParameter[];
  channelNames: string[];
  loading: boolean;
  chartStyle?: CSSProperties;
  showRepetitions?: boolean;
  /** Zero-based full raster pass; labels shown to users are one-based. */
  repetition?: number;
}

const escapeHtml = (text: string) =>
  text.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] ??
      char,
  );
const numericLabel = (value: string) => String(Number(Number(value).toPrecision(6)));

export function ViewerHeatmap({
  experimentData,
  scanParameters,
  channelNames,
  loading,
  chartStyle,
  showRepetitions = false,
  repetition,
}: ViewerHeatmapProps) {
  const [view, setView] = useState<"heatmap" | "curves">("heatmap");
  const [horizontalAxis, setHorizontalAxis] = useState<OverlayHorizontalAxis>("x");
  const [sliceSelection, setSliceSelection] = useState<{
    x: number[] | null;
    y: number[] | null;
  }>({ x: null, y: null });
  const [selectedChannel, setSelectedChannel] = useState<string>();
  const [selectedRepetition, setSelectedRepetition] = useState(0);
  const [chart, setChart] = useState<ECharts | null>(null);
  const allData = useMemo(
    () => buildHeatmapData(experimentData, scanParameters, channelNames),
    [experimentData, scanParameters, channelNames],
  );
  const activeRepetition = showRepetitions
    ? (repetition ??
      (allData.repetitions.includes(selectedRepetition)
        ? selectedRepetition
        : allData.repetitions[0]))
    : undefined;
  const model = useMemo(
    () =>
      activeRepetition === undefined
        ? allData
        : buildHeatmapData(
            experimentData,
            scanParameters,
            channelNames,
            activeRepetition,
          ),
    [allData, experimentData, scanParameters, channelNames, activeRepetition],
  );
  const activeChannel =
    model.channels.find((channel) => channel.name === selectedChannel) ??
    model.channels[0];
  const channelName = activeChannel?.name;
  const option = useMemo<EChartsOption>(() => {
    const xCategories = heatmapAxisCategories(model.xAxis);
    const yCategories = heatmapAxisCategories(model.yAxis);
    const formatCoordinate = (
      index: number,
      realtime: boolean,
      categories: string[],
    ) =>
      realtime ? formatDateTime(categories[index]) : numericLabel(categories[index]);
    return {
      textStyle: CHART_TEXT_STYLE,
      animation: false,
      legend: {
        type: "scroll",
        top: 0,
        left: "center",
        selectedMode: "single",
        data: model.channels.map((channel) => channel.name),
        selected: Object.fromEntries(
          model.channels.map((channel) => [channel.name, channel.name === channelName]),
        ),
      },
      grid: { ...CHART_GRID, top: 36, right: 96, bottom: 20 },
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as { seriesName?: string; value?: number[] };
          const [x, y, value, count] = item.value ?? [];
          if (![x, y, value].every(Number.isFinite)) return "";
          return [
            `${escapeHtml(model.xAxis.name)}: ${escapeHtml(formatCoordinate(x, model.xAxis.realtime, xCategories))}`,
            `${escapeHtml(model.yAxis.name)}: ${escapeHtml(formatCoordinate(y, model.yAxis.realtime, yCategories))}`,
            `${escapeHtml(item.seriesName ?? "")}: <b>${value}</b>`,
            count > 1 ? `Mean of ${count} observations` : undefined,
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      xAxis: {
        ...CHART_AXIS_NAME,
        type: "category",
        name: model.xAxis.name,
        data: xCategories,
        axisLabel: {
          hideOverlap: true,
          formatter: model.xAxis.realtime ? formatDateTime : numericLabel,
        },
        splitArea: { show: true },
      },
      yAxis: {
        ...CHART_AXIS_NAME,
        type: "category",
        name: model.yAxis.name,
        data: yCategories,
        axisLabel: {
          hideOverlap: true,
          formatter: model.yAxis.realtime ? formatDateTime : numericLabel,
        },
        splitArea: { show: true },
      },
      series: model.channels.map((channel) => ({
        id: `viewer-heatmap-${channel.name}`,
        name: channel.name,
        type: "heatmap" as const,
        data: heatmapSeriesData(channel, model.xAxis, model.yAxis),
        encode: { x: 0, y: 1, value: 2 },
        emphasis: { itemStyle: { borderColor: "#333", borderWidth: 1 } },
        animation: false,
      })),
      visualMap: {
        type: "continuous",
        dimension: 2,
        show: true,
        calculable: true,
        min: activeChannel?.min ?? 0,
        max: activeChannel?.max ?? 1,
        orient: "vertical",
        right: 8,
        top: "middle",
        itemWidth: 14,
        textStyle: { fontSize: 11 },
        inRange: { color: ["#313695", "#1483d5", "#73bf7f", "#fcbe3d", "#ffff00"] },
      },
    };
  }, [model, channelName, activeChannel]);
  const chartReady = useCallback((instance: ECharts) => setChart(instance), []);
  useEffect(() => {
    if (!chart || chart.isDisposed() || view !== "heatmap") return;
    const handleSelection = (event: unknown) => {
      const name = (event as { name?: string }).name;
      if (typeof name === "string") setSelectedChannel(name);
    };
    chart.on("legendselectchanged", handleSelection);
    return () => {
      if (!chart.isDisposed()) chart.off("legendselectchanged", handleSelection);
    };
  }, [chart, view]);

  if (model.error) return <Alert severity="warning">{model.error}</Alert>;
  const repetitionOptions =
    repetition !== undefined && !allData.repetitions.includes(repetition)
      ? [...allData.repetitions, repetition].sort((a, b) => a - b)
      : allData.repetitions;
  return (
    <Box>
      <Stack
        direction="row"
        spacing={1}
        useFlexGap
        flexWrap="wrap"
        alignItems="center"
        sx={{ mb: 1 }}
      >
        <ToggleButtonGroup
          size="small"
          exclusive
          value={view}
          aria-label="2D plot view"
          onChange={(_, value: "heatmap" | "curves" | null) => {
            if (value) setView(value);
          }}
        >
          <ToggleButton value="heatmap">Heatmap</ToggleButton>
          <ToggleButton value="curves">Overlaid curves</ToggleButton>
        </ToggleButtonGroup>
        {view === "curves" && (
          <>
            <FormControl size="small" sx={{ minWidth: 200 }}>
              <InputLabel id="overlay-horizontal-label">Horizontal axis</InputLabel>
              <Select
                labelId="overlay-horizontal-label"
                label="Horizontal axis"
                value={horizontalAxis}
                onChange={(event) =>
                  setHorizontalAxis(event.target.value as OverlayHorizontalAxis)
                }
              >
                <MenuItem value="x">{model.xAxis.name} (X)</MenuItem>
                <MenuItem value="y">{model.yAxis.name} (Y)</MenuItem>
              </Select>
            </FormControl>
            {model.channels.length > 1 && (
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="overlay-channel-label">Channel</InputLabel>
                <Select
                  labelId="overlay-channel-label"
                  label="Channel"
                  value={channelName ?? ""}
                  onChange={(event) => setSelectedChannel(event.target.value)}
                >
                  {model.channels.map((channel) => (
                    <MenuItem key={channel.name} value={channel.name}>
                      {channel.name}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
            )}
          </>
        )}
      </Stack>
      {showRepetitions && repetitionOptions.length > 0 && (
        <FormControl size="small" sx={{ mb: 1, minWidth: 180 }}>
          <InputLabel id="heatmap-repetition-label">Repetition</InputLabel>
          <Select
            labelId="heatmap-repetition-label"
            label="Repetition"
            value={activeRepetition ?? ""}
            disabled={repetition !== undefined}
            onChange={(event) => setSelectedRepetition(Number(event.target.value))}
          >
            {repetitionOptions.map((ordinal) => (
              <MenuItem key={ordinal} value={ordinal}>
                Repetition {ordinal + 1}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      )}
      {!loading && !activeChannel?.cells.length && (
        <Typography variant="body2" color="text.secondary" sx={{ px: 1, pb: 1 }}>
          No observed cells for this channel
          {activeRepetition !== undefined ? " and repetition" : ""}.
        </Typography>
      )}
      {view === "curves" ? (
        <ViewerOverlayCurves
          model={model}
          channelName={channelName ?? ""}
          horizontalAxis={horizontalAxis}
          selectedValues={sliceSelection[horizontalAxis]}
          onSelectionChange={(values) =>
            setSliceSelection((current) => ({ ...current, [horizontalAxis]: values }))
          }
          loading={loading}
          chartStyle={chartStyle}
        />
      ) : (
        <ViewerChart
          key="heatmap"
          option={option}
          style={chartStyle}
          loading={loading}
          onChartReady={chartReady}
        />
      )}
    </Box>
  );
}

export default ViewerHeatmap;
