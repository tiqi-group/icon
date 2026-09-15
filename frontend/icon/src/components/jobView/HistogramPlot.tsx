import { useCallback, useMemo, useState } from "react";
import type { ECharts } from "echarts/core";
import { ReactECharts } from "../ReactEcharts";
import { ExperimentData } from "../../types/ExperimentData";
import type { EChartsOption } from "echarts/types/dist/shared";
import { useNotifications } from "@toolpad/core";
import {
  CHART_AXIS_NAME,
  CHART_GRID,
  CHART_HEIGHT,
  CHART_LEGEND,
  CHART_TEXT_STYLE,
  chartTitle,
  chartToolbox,
} from "../../utils/chartLayout";

interface HistogramPlotProps {
  experimentData: ExperimentData;
  channelNames: string[];
  title: string;
  subtitle: string;
  loading: boolean;
}

export const HistogramPlot = ({
  experimentData,
  title,
  subtitle,
  loading,
  channelNames,
}: HistogramPlotProps) => {
  const [chart, setChart] = useState<ECharts | null>(null);
  const notifications = useNotifications();

  const latestPerChannel: Record<string, number[]> = {};
  const sc = experimentData?.readouts?.shot_channels ?? {};

  for (const [channelName, groups] of Object.entries(sc)) {
    if (!groups || !channelNames.includes(channelName)) continue;

    // Get the latest key by calculating the max of the available keys
    const keys = Object.keys(groups).map(Number);
    const latestKey = String(Math.max(...keys));

    latestPerChannel[channelName] = groups[latestKey];
  }

  // Build the categories and frequency data
  let categories: string[] = [];
  const seriesData: { name: string; data: number[] }[] = [];

  const allArrays = Object.values(latestPerChannel);
  if (allArrays.length > 0) {
    const globalMax = Math.max(...allArrays.map((a) => Math.max(...a)));
    const rangeMax = Math.max(80, globalMax); // ensure at least 0..80

    // categories are the integer values from 0..rangeMax
    categories = Array.from({ length: rangeMax + 1 }, (_, i) => String(i));

    for (const [name, arr] of Object.entries(latestPerChannel)) {
      const counts = new Array(rangeMax + 1).fill(0);
      for (const v of arr) {
        counts[v]++;
      }
      seriesData.push({ name, data: counts });
    }
  }

  const option = useMemo<EChartsOption | undefined>(() => {
    if (categories.length === 0 || seriesData.length === 0) return undefined;

    return {
      title: chartTitle(title, subtitle),
      textStyle: CHART_TEXT_STYLE,
      tooltip: { trigger: "axis" },
      toolbox: chartToolbox(chart, notifications.show),
      animation: false,
      legend: CHART_LEGEND,
      grid: CHART_GRID,
      xAxis: {
        type: "category",
        data: categories,
        name: "Ion Counts",
        ...CHART_AXIS_NAME,
        axisLabel: {
          // categories are the integers 0..rangeMax, so labelling every tenth
          // index gives round, evenly spaced labels
          interval: (index: number) => index % 10 === 0,
          hideOverlap: true,
        },
      },
      yAxis: {
        type: "value",
        name: "Count",
        ...CHART_AXIS_NAME,
      },
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
        },
      ],
      series: seriesData.map((s) => ({
        type: "bar",
        name: s.name,
        data: s.data,
        barMaxWidth: 22,
        emphasis: { focus: "series" },
        large: true,
      })),
    };
  }, [title, subtitle, categories, seriesData, chart, notifications.show]);

  const empty = !option;

  const updateChart = useCallback(
    (chart: ECharts) => {
      setChart(chart);
    },
    [setChart],
  );

  return (
    <>
      {empty ? (
        loading ? (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100%",
              fontSize: "1.2rem",
              color: "#888",
            }}
          >
            Loading...
          </div>
        ) : (
          <div
            style={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              height: "100%",
              fontSize: "1.2rem",
              color: "#888",
            }}
          >
            No data.
          </div>
        )
      ) : (
        <ReactECharts
          option={option}
          loading={loading}
          style={{ width: "100%", height: CHART_HEIGHT }}
          onChartReady={updateChart}
        />
      )}
    </>
  );
};

export default HistogramPlot;
