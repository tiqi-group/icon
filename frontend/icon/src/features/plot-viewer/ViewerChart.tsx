import { createContext, useContext, useEffect, useRef, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  useColorScheme,
} from "@mui/material";
import * as echarts from "echarts/core";
import { BrushComponent, TitleComponent } from "echarts/components";
import type { ECharts } from "echarts/core";
import type { EChartsOption } from "echarts";
import type { ReactEChartsProps } from "../../components/ReactEcharts";
import { brushZoomRanges, scaleZoomRanges, type ZoomAxes } from "./viewerZoom";

import { chartTitle } from "../../utils/chartLayout";
import { ViewerPlotIdentityContext } from "./viewerPlotIdentity";
import { ViewerAxisLimits } from "./ViewerAxisLimits";
import {
  AUTO_BOUNDS,
  axisBounds,
  axisInputType,
  resolveAxisBounds,
  type ViewerAxis,
  type ViewerBounds,
} from "./viewerAxisBounds";

echarts.use([BrushComponent, TitleComponent]);

export const ViewerInteractionContext = createContext({
  holdView: () => {},
  resetToken: 0,
});

export function ViewerChart({
  option,
  style,
  loading,
  onChartReady,
}: ReactEChartsProps) {
  const container = useRef<HTMLDivElement>(null);
  const instance = useRef<ECharts | null>(null);
  const { mode } = useColorScheme();
  const interaction = useContext(ViewerInteractionContext);
  const identity = useContext(ViewerPlotIdentityContext);
  const [bounds, setBounds] = useState<ViewerBounds>(AUTO_BOUNDS);
  const [axisWarning, setAxisWarning] = useState<string | null>(null);
  const xAxis = [option.xAxis].flat()[0] as ViewerAxis | undefined;
  const yAxis = [option.yAxis].flat()[0] as ViewerAxis | undefined;
  const [axes, setAxes] = useState<ZoomAxes>("both");
  const [dragMode, setDragMode] = useState<"pan" | "box">("pan");
  const latest = useRef({ onChartReady, holdView: interaction.holdView });
  latest.current = { onChartReady, holdView: interaction.holdView };

  useEffect(() => {
    if (!container.current) return;
    const chart = echarts.init(container.current, mode);
    instance.current = chart;
    chart.on("datazoom", () => {
      latest.current.holdView();
      chart.dispatchAction({ type: "hideTip" });
    });
    chart.on("brushEnd", (event: unknown) => {
      const { areas } = event as { areas?: Parameters<typeof brushZoomRanges>[0][] };
      const batch = brushZoomRanges(areas?.[0]);
      chart.dispatchAction({ type: "brush", areas: [] }, { silent: true });
      if (!batch.length) return;
      latest.current.holdView();
      chart.dispatchAction({ type: "dataZoom", batch });
      // Return to pan after selection so the next drag can reposition the view.
      setDragMode("pan");
    });
    latest.current.onChartReady?.(chart);
    let frame = 0;
    const resize = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => chart.resize());
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container.current);
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDragMode("pan");
    };
    window.addEventListener("keydown", escape);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      window.removeEventListener("keydown", escape);
      chart.dispose();
      instance.current = null;
    };
  }, [mode]);

  useEffect(() => {
    const axesOption = option as EChartsOption;
    const xBounds = resolveAxisBounds(xAxis, bounds.xMin, bounds.xMax);
    const yBounds = resolveAxisBounds(yAxis, bounds.yMin, bounds.yMax);
    if (!xBounds.valid || !yBounds.valid) {
      // Do not replace the last valid chart with unrelated or silently clamped data.
      setAxisWarning(
        !xBounds.valid ? xBounds.error : !yBounds.valid ? yBounds.error : "",
      );
      return;
    }
    setAxisWarning(null);
    // Merge preserves public zoom/legend state. Shared charts and PR #171's
    // toolbox/history behavior remain independent of this viewer.
    instance.current?.setOption(
      {
        ...option,
        ...(identity
          ? {
              title: {
                ...chartTitle(identity.title, identity.subtitle),
                subtextStyle: { fontSize: 11, lineHeight: 14 },
              },
              legend: [axesOption.legend]
                .flat()
                .filter(Boolean)
                .map((legend) => ({ ...legend, top: 58 })),
              grid: [axesOption.grid]
                .flat()
                .filter(Boolean)
                .map((grid) => ({ ...grid, top: 86 })),
            }
          : {}),
        // Brush boundaries are arbitrary values; regular ticks stay readable.
        xAxis: [axesOption.xAxis].flat().flatMap((axis) =>
          axis
            ? [
                {
                  ...axis,
                  ...xBounds.bounds,
                  axisLabel: {
                    ...axis.axisLabel,
                    showMinLabel: axis.type === "category",
                    showMaxLabel: axis.type === "category",
                  },
                },
              ]
            : [],
        ),
        yAxis: [axesOption.yAxis].flat().flatMap((axis) =>
          axis
            ? [
                {
                  ...axis,
                  ...yBounds.bounds,
                  axisLabel: {
                    ...axis.axisLabel,
                    showMinLabel: axis.type === "category",
                    showMaxLabel: axis.type === "category",
                  },
                },
              ]
            : [],
        ),
        backgroundColor: mode === "dark" ? "#1e1e1e" : "#ffffff",
        toolbox: { show: false },
        brush: {
          toolbox: [],
          xAxisIndex: 0,
          yAxisIndex: 0,
          seriesIndex: [],
          brushType: false,
          brushMode: "single",
          transformable: false,
          brushStyle: {
            color: "rgba(25, 118, 210, 0.15)",
            borderColor: "#1976d2",
            borderWidth: 1,
          },
        },
        dataZoom: [
          {
            id: "viewer-x",
            type: "inside",
            xAxisIndex: 0,
            filterMode: "none",
            disabled: axes === "y",
            zoomOnMouseWheel: dragMode === "pan",
            moveOnMouseMove: dragMode === "pan",
            moveOnMouseWheel: false,
          },
          {
            id: "viewer-y",
            type: "inside",
            yAxisIndex: 0,
            filterMode: "none",
            disabled: axes === "x",
            zoomOnMouseWheel: dragMode === "pan",
            moveOnMouseMove: dragMode === "pan",
            moveOnMouseWheel: false,
          },
        ],
      },
      { replaceMerge: ["series"], lazyUpdate: false },
    );
    instance.current?.dispatchAction(
      {
        type: "takeGlobalCursor",
        key: "brush",
        brushOption: {
          brushType:
            dragMode === "box"
              ? axes === "both"
                ? "rect"
                : axes === "x"
                  ? "lineX"
                  : "lineY"
              : false,
          brushMode: "single",
        },
      },
      { silent: true },
    );
    if (dragMode === "pan")
      instance.current?.dispatchAction({ type: "brush", areas: [] }, { silent: true });
  }, [option, mode, axes, dragMode, bounds, xAxis, yAxis, identity]);

  const reset = () => {
    setDragMode("pan");
    instance.current?.dispatchAction(
      {
        type: "dataZoom",
        batch: [
          { dataZoomId: "viewer-x", start: 0, end: 100 },
          { dataZoomId: "viewer-y", start: 0, end: 100 },
        ],
      },
      { silent: true },
    );
  };
  useEffect(reset, [interaction.resetToken, mode, bounds]);
  const applyBounds = (next: ViewerBounds): string | null => {
    try {
      axisBounds(xAxis, next.xMin, next.xMax);
      axisBounds(yAxis, next.yMin, next.yMax);
      if (
        Object.keys(next).every(
          (key) =>
            next[key as keyof ViewerBounds] === bounds[key as keyof ViewerBounds],
        )
      )
        return null;
      if (next.xMin !== bounds.xMin || next.xMax !== bounds.xMax)
        latest.current.holdView();
      setBounds(next);
      return null;
    } catch (error) {
      return error instanceof Error ? error.message : String(error);
    }
  };
  useEffect(() => {
    if (loading) instance.current?.showLoading();
    else instance.current?.hideLoading();
  }, [loading, mode]);

  const zoom = (factor: number) => {
    const chart = instance.current;
    if (!chart) return;
    latest.current.holdView();
    setDragMode("pan");
    const ranges = chart.getOption().dataZoom as {
      id: string;
      start: number;
      end: number;
    }[];
    chart.dispatchAction({
      type: "dataZoom",
      batch: scaleZoomRanges(ranges, axes, factor),
    });
  };

  return (
    <Box
      sx={{
        ...style,
        height: "auto",
        minHeight: style?.height ?? 360,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Stack
        direction="row"
        gap={1}
        flexWrap="wrap"
        alignItems="center"
        sx={{ px: 1, pb: 1 }}
      >
        <ToggleButtonGroup
          size="small"
          exclusive
          value={dragMode}
          aria-label="Drag action"
          onChange={(_, value: "pan" | "box" | null) => {
            if (!value) return;
            if (value === "box") latest.current.holdView();
            setDragMode(value);
          }}
        >
          <ToggleButton value="pan">Pan</ToggleButton>
          <ToggleButton value="box">Box zoom</ToggleButton>
        </ToggleButtonGroup>
        <ToggleButtonGroup
          size="small"
          exclusive
          value={axes}
          aria-label="Axes to zoom or pan"
          onChange={(_, value: ZoomAxes | null) => {
            if (value) setAxes(value);
          }}
        >
          <ToggleButton value="both">Both axes</ToggleButton>
          <ToggleButton value="x">X only</ToggleButton>
          <ToggleButton value="y">Y only</ToggleButton>
        </ToggleButtonGroup>
        <Button size="small" variant="outlined" onClick={() => zoom(0.5)}>
          Zoom in
        </Button>
        <Button size="small" variant="outlined" onClick={() => zoom(2)}>
          Zoom out
        </Button>
        <Button
          size="small"
          onClick={() => {
            setBounds(AUTO_BOUNDS);
            reset();
          }}
        >
          Reset axes
        </Button>
      </Stack>
      {axisWarning && (
        <Alert severity="warning" sx={{ mx: 1, mb: 1 }}>
          New data cannot be displayed with the current axis limits: {axisWarning} Chart
          updates are paused. Adjust the limits or choose Reset axes.
        </Alert>
      )}
      <ViewerAxisLimits
        value={bounds}
        xType={axisInputType(xAxis)}
        yType={axisInputType(yAxis)}
        onApply={applyBounds}
      />
      <Typography
        variant="caption"
        color="text.secondary"
        sx={{ px: 1, pb: 1 }}
        aria-live="polite"
      >
        {dragMode === "box"
          ? axes === "both"
            ? "Drag any rectangle to zoom; X and Y scale independently. Esc cancels."
            : `Drag to select a ${axes.toUpperCase()} range; the other axis stays fixed. Esc cancels.`
          : "Scroll to zoom · drag to pan on the selected axes · hover to read values"}
      </Typography>
      <div
        ref={container}
        style={{ flex: 1, minHeight: 300, width: "100%" }}
        role="img"
        aria-label={
          identity ? `${identity.title}. ${identity.subtitle}` : "Selected plot"
        }
      />
    </Box>
  );
}
