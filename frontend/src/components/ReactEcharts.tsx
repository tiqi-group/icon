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
}

interface DataZoomBatchItem {
  dataZoomId?: string;
  start?: number;
  end?: number;
  startValue?: number;
  endValue?: number;
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
}: ReactEChartsProps) {
  const chartDivRef = useRef<HTMLDivElement>(null);
  const chartInstanceRef = useRef<ECharts | null>(null);
  // Last zoom window per dataZoom component, captured from user interactions so
  // it can be re-applied after every setOption({ notMerge: true }) re-draw.
  const zoomStateRef = useRef<Record<string, DataZoomBatchItem>>({});
  const { mode } = useColorScheme();

  useEffect(() => {
    if (!chartDivRef.current) return;

    const chart = echarts.init(chartDivRef.current, mode);
    chartInstanceRef.current = chart;

    chart.on("datazoom", (params) => {
      const payload = params as { batch?: DataZoomBatchItem[] } & DataZoomBatchItem;
      for (const item of payload.batch ?? [payload]) {
        if (!item.dataZoomId) continue;
        zoomStateRef.current[item.dataZoomId] = {
          dataZoomId: item.dataZoomId,
          start: item.start,
          end: item.end,
          startValue: item.startValue,
          endValue: item.endValue,
        };
      }
    });
    chart.on("restore", () => {
      zoomStateRef.current = {};
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

  useEffect(() => {
    const chart = chartInstanceRef.current;
    if (!chart) return;

    chart.setOption(
      {
        ...option,
        backgroundColor: mode === "dark" ? "#1e1e1e" : "#ffffff",
      },
      { notMerge: true },
    );

    // notMerge re-creates the dataZoom components with a full-range window;
    // re-apply the last zoom so it survives re-draws while a scan is running.
    // Stale ids (e.g. after switching to an option without zoom) are a no-op.
    const batch = Object.values(zoomStateRef.current);
    if (batch.length > 0) {
      chart.dispatchAction({ type: "dataZoom", batch }, { silent: true });
    }
  }, [option, mode]);

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
