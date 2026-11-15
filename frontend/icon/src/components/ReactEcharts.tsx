import { useRef, useEffect } from "react";
import * as echarts from "echarts/core";
import { BarChart, HeatmapChart, LineChart } from "echarts/charts";
import {
  LegendComponent,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  DataZoomComponent,
  ToolboxComponent,
  VisualMapComponent,
} from "echarts/components";
import type { CSSProperties } from "react";
import type { EChartsCoreOption, ECharts } from "echarts/core";
import { useColorScheme } from "@mui/material";
import { CanvasRenderer } from "echarts/renderers";

export interface ReactEChartsProps {
  option: EChartsCoreOption;
  style?: CSSProperties;
  loading?: boolean;
  /** Called once after the chart is created */
  onChartReady?: (chart: ECharts) => void;
  /**
   * Merge each option into the chart instead of replacing it, which keeps the legend
   * selection, zoom, hover and tooltip state. Series are matched by id and removed
   * when missing, so every series needs an id, and every option has to set all keys
   * that any option sets.
   */
  merge?: boolean;
}

echarts.use([
  LegendComponent,
  LineChart,
  GridComponent,
  TooltipComponent,
  TitleComponent,
  DataZoomComponent,
  ToolboxComponent,
  CanvasRenderer,
  HeatmapChart,
  VisualMapComponent,
  BarChart,
]);

export function ReactECharts({
  option,
  style,
  loading,
  onChartReady,
  merge = false,
}: ReactEChartsProps) {
  const chartDivRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ECharts | null>(null);
  const { mode } = useColorScheme();
  // While the mouse button is held on the chart, the newest option waits here
  const pressedRef = useRef(false);
  const pendingUpdateRef = useRef<(() => void) | null>(null);
  // Position of the mouse while it is over the chart
  const pointerRef = useRef<{ x: number; y: number } | null>(null);

  useEffect(() => {
    if (!chartDivRef.current) return;

    const chart = echarts.init(chartDivRef.current, mode);
    chartInstanceRef.current = chart;
    pointerRef.current = null;
    const zr = chart.getZr();
    zr.on("mousemove", (e: { offsetX: number; offsetY: number }) => {
      pointerRef.current = { x: e.offsetX, y: e.offsetY };
    });
    zr.on("globalout", () => {
      pointerRef.current = null;
    });

    if (onChartReady) {
      onChartReady(chart);
    }

    const resizeChart = () => chart.resize();
    window.addEventListener("resize", resizeChart);

    return () => {
      chart.dispose();
      chartInstanceRef.current = null;
      window.removeEventListener("resize", resizeChart);
    };
  }, [mode, onChartReady]);

  // setOption rebuilds the legend and toolbox, and zrender drops a click whose
  // mousedown and mouseup hit different elements. Updates arriving during a click,
  // e.g. live data points, are therefore held until the click has been handled.
  useEffect(() => {
    const update = () => {
      const chart = chartInstanceRef.current;
      if (!chart) return;
      chart.setOption(
        {
          ...option,
          backgroundColor: mode === "dark" ? "#1e1e1e" : "#ffffff",
        },
        merge ? { replaceMerge: ["series"] } : { notMerge: true },
      );
      // Replacing the option also replaces the tooltip, which then forgets where the
      // mouse is. Show it again there; a merged chart keeps its tooltip by itself.
      const pointer = pointerRef.current;
      if (!merge && pointer)
        chart.dispatchAction({ type: "showTip", x: pointer.x, y: pointer.y });
    };
    if (pressedRef.current) pendingUpdateRef.current = update;
    else update();
  }, [option, mode, merge]);

  useEffect(() => {
    const chartDiv = chartDivRef.current;
    if (!chartDiv) return;

    let flushTimer: number | undefined;
    const press = (event: PointerEvent) => {
      if (event.button === 0) pressedRef.current = true;
    };
    const release = () => {
      if (!pressedRef.current) return;
      pressedRef.current = false;
      // Apply the held update after the click event following pointerup
      flushTimer = window.setTimeout(() => {
        if (pressedRef.current) return;
        const update = pendingUpdateRef.current;
        pendingUpdateRef.current = null;
        update?.();
      });
    };

    chartDiv.addEventListener("pointerdown", press);
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", release);
    window.addEventListener("blur", release);
    return () => {
      chartDiv.removeEventListener("pointerdown", press);
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", release);
      window.removeEventListener("blur", release);
      window.clearTimeout(flushTimer);
    };
  }, []);

  useEffect(() => {
    if (!chartInstanceRef.current) return;

    if (loading) chartInstanceRef.current.showLoading();
    else chartInstanceRef.current.hideLoading();
  }, [loading]);

  return (
    <div
      ref={chartDivRef}
      style={{
        width: "100%",
        height: "300px",
        ...style,
      }}
    />
  );
}
