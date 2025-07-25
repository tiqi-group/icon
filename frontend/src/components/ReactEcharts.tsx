import { useRef, useEffect, useMemo } from "react";
import * as echarts from "echarts/core";
import { HeatmapChart, LineChart } from "echarts/charts";
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
import type { EChartsCoreOption, ECharts, SetOptionOpts } from "echarts/core";
import { useColorScheme } from "@mui/material";
import { CanvasRenderer } from "echarts/renderers";

export interface ReactEChartsProps {
  option: EChartsCoreOption;
  style?: CSSProperties;
  settings?: SetOptionOpts;
  loading?: boolean;
  /** Called once after the chart is created */
  onChartReady?: (chart: ECharts) => void;
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
]);

export function ReactECharts({
  option,
  style,
  settings,
  loading,
  onChartReady,
}: ReactEChartsProps) {
  const chartDivRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ECharts | null>(null);
  const { mode } = useColorScheme();

  const updatedOption = useMemo<EChartsCoreOption>(() => {
    return {
      ...option,
      backgroundColor: mode === "dark" ? "#1e1e1e" : "#ffffff",
    };
  }, [option, mode]);

  useEffect(() => {
    if (!chartDivRef.current) return;

    const chart = echarts.init(chartDivRef.current, mode);
    chartInstanceRef.current = chart;

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

  useEffect(() => {
    chartInstanceRef.current?.setOption(updatedOption, settings);
  }, [updatedOption, settings]);

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
