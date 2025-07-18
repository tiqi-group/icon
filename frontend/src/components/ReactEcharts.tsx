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

export function ReactECharts({ option, style, settings, loading }: ReactEChartsProps) {
  const chartRef = useRef<HTMLDivElement>(null);
  const { mode } = useColorScheme();
  if (!mode) {
    return;
  }

  // Dynamically set background color based on theme mode
  const updatedOption = useMemo<EChartsCoreOption>(() => {
    return {
      ...option,
      backgroundColor: mode === "dark" ? "#1e1e1e" : "#ffffff",
    };
  }, [option, mode]);

  useEffect(() => {
    let chart: ECharts | undefined;
    if (chartRef.current !== null) {
      chart = echarts.init(chartRef.current, mode);
    }

    function resizeChart() {
      chart?.resize();
    }
    window.addEventListener("resize", resizeChart);

    return () => {
      chart?.dispose();
      window.removeEventListener("resize", resizeChart);
    };
  }, [mode]);

  useEffect(() => {
    if (chartRef.current !== null) {
      const chart = echarts.getInstanceByDom(chartRef.current);
      if (chart !== undefined) {
        chart.setOption(updatedOption, settings);
      }
    }
  }, [updatedOption, settings, mode]);

  useEffect(() => {
    if (chartRef.current !== null) {
      const chart = echarts.getInstanceByDom(chartRef.current);
      if (chart !== undefined) {
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        loading === true ? chart.showLoading() : chart.hideLoading();
      }
    }
  }, [loading, mode]);

  return (
    <div
      ref={chartRef}
      style={{
        width: "100%",
        height: "300px",
        ...style,
      }}
    />
  );
}
