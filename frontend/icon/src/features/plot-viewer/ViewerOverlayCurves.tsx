import { useMemo } from "react";
import type { CSSProperties } from "react";
import { Alert, Box } from "@mui/material";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import type { EChartsOption } from "echarts";
import { CHART_AXIS_NAME, CHART_GRID, CHART_TEXT_STYLE } from "../../utils/chartLayout";
import type { HeatmapData } from "./heatmapData";
import { availableCurveSlices, buildOverlayCurves } from "./overlayCurveData";
import type { OverlayHorizontalAxis } from "./overlayCurveData";
import { ViewerChart } from "./ViewerChart";
import { ViewerSliceSelector } from "./ViewerSliceSelector";

echarts.use([LineChart]);

const DEFAULT_SLICES = 12;
const MAX_SLICES = 32;
const COLORS = [
  "#0068ad",
  "#c04b00",
  "#148244",
  "#a13b9b",
  "#b08200",
  "#ca3959",
  "#008b91",
  "#6952b5",
  "#6d7034",
  "#765541",
  "#4f7c9b",
  "#9e5270",
];
const escapeHtml = (text: string) =>
  text.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] ??
      char,
  );

// Coordinate-based colors stay stable when a slice is hidden or new data arrives.
function sliceColor(value: number): string {
  let hash = 0;
  for (const character of String(value))
    hash = ((hash << 5) - hash + character.charCodeAt(0)) | 0;
  return COLORS[(hash >>> 0) % COLORS.length];
}

interface ViewerOverlayCurvesProps {
  model: HeatmapData;
  channelName: string;
  horizontalAxis: OverlayHorizontalAxis;
  selectedValues: number[] | null;
  onSelectionChange: (values: number[] | null) => void;
  loading: boolean;
  chartStyle?: CSSProperties;
}

export function ViewerOverlayCurves({
  model,
  channelName,
  horizontalAxis,
  selectedValues,
  onSelectionChange,
  loading,
  chartStyle,
}: ViewerOverlayCurvesProps) {
  const available = useMemo(
    () => availableCurveSlices(model, channelName, horizontalAxis),
    [model, channelName, horizontalAxis],
  );
  const selected = useMemo(() => {
    if (selectedValues === null) return available.slice(0, DEFAULT_SLICES);
    const availableSet = new Set(available);
    return selectedValues.filter((value) => availableSet.has(value));
  }, [available, selectedValues]);
  const curves = useMemo(
    () => buildOverlayCurves(model, channelName, horizontalAxis, selected),
    [model, channelName, horizontalAxis, selected],
  );
  const horizontal = horizontalAxis === "x" ? model.xAxis : model.yAxis;
  const fixed = horizontalAxis === "x" ? model.yAxis : model.xAxis;
  const sliceValueLabel = (value: number) =>
    fixed.realtime ? new Date(value).toISOString() : String(value);
  const option = useMemo<EChartsOption>(
    () => ({
      textStyle: CHART_TEXT_STYLE,
      animation: false,
      legend: {
        type: "scroll",
        top: 0,
        left: "center",
        selectedMode: false,
        data: curves.map((curve) => curve.label),
        formatter: (name: string) => {
          const curve = curves.find((candidate) => candidate.label === name);
          return curve
            ? fixed.realtime
              ? new Date(curve.fixedValue).toISOString()
              : String(curve.fixedValue)
            : name;
        },
      },
      grid: { ...CHART_GRID, top: 36, bottom: 20 },
      xAxis: {
        ...CHART_AXIS_NAME,
        type: horizontal.realtime ? "time" : "value",
        name: horizontal.name,
        scale: true,
        axisLabel: { hideOverlap: true },
      },
      yAxis: {
        ...CHART_AXIS_NAME,
        type: "value",
        name: channelName,
        scale: true,
        axisLabel: { hideOverlap: true },
      },
      tooltip: {
        trigger: "item",
        formatter: (params: unknown) => {
          const item = params as {
            seriesName?: string;
            value?: [number, number | null, number];
          };
          const [coordinate, value, count] = item.value ?? [];
          if (!Number.isFinite(coordinate) || value === null || !Number.isFinite(value))
            return "";
          return [
            escapeHtml(item.seriesName ?? ""),
            `${escapeHtml(horizontal.name)}: ${horizontal.realtime ? new Date(coordinate!).toISOString() : coordinate}`,
            `${escapeHtml(channelName)}: <b>${value}</b>`,
            count && count > 1 ? `Mean of ${count} observations` : undefined,
          ]
            .filter(Boolean)
            .join("<br/>");
        },
      },
      series: curves.map((curve) => ({
        id: curve.id,
        name: curve.label,
        type: "line",
        data: curve.points,
        encode: { x: 0, y: 1 },
        connectNulls: false,
        showSymbol: true,
        symbolSize: 5,
        smooth: false,
        itemStyle: { color: sliceColor(curve.fixedValue) },
        lineStyle: { width: 1.5 },
        emphasis: { focus: "series" },
        animation: false,
      })),
    }),
    [curves, horizontal, fixed.realtime, channelName],
  );

  return (
    <Box>
      <ViewerSliceSelector
        parameterName={fixed.name}
        available={available}
        selected={selected}
        formatValue={sliceValueLabel}
        maxSlices={MAX_SLICES}
        defaultSlices={DEFAULT_SLICES}
        onChange={onSelectionChange}
      />
      {selected.length === 0 && !loading && (
        <Alert severity="info" sx={{ mb: 1 }}>
          {available.length
            ? "Select at least one slice to compare."
            : "No observed slices for this channel and repetition yet."}
        </Alert>
      )}
      <ViewerChart
        key={`${horizontalAxis}:${channelName}`}
        option={option}
        style={chartStyle}
        loading={loading}
      />
    </Box>
  );
}
