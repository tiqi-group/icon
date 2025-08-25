import { useMemo, useRef } from "react";
import type { ECharts } from "echarts/core";
import { ReactECharts } from "../ReactEcharts";
import { ExperimentData } from "../../types/ExperimentData";
import type { EChartsOption } from "echarts/types/dist/shared";
import { copyEChartsToClipboard } from "../../utils/copyEChartsToClipboard";
import { useNotifications } from "@toolpad/core";

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
  const chartRef = useRef<ECharts | null>(null);
  const notifications = useNotifications();

  const latestPerChannel: Record<string, number[]> = {};
  const sc = experimentData?.shot_channels ?? {};

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
      title: {
        text: title,
        left: "center",
        subtext: subtitle,
        subtextStyle: {
          lineHeight: 0,
        },
        top: "-1%",
      },
      textStyle: { fontFamily: "sans-serif", fontSize: 12 },
      tooltip: { trigger: "axis" },
      toolbox: {
        top: -6,
        feature: {
          dataZoom: { yAxisIndex: "none" },
          myCopyToClipboard: {
            show: true,
            title: "Copy to Clipboard",
            icon: "path://M48.7643 38.2962H100.5807a6.0158 6.0158 0 0 1 6.0158 6.0158V115.2992a6.0158 6.0158 0 0 1-6.0158 6.0158H48.7643a6.0158 6.0158 0 0 1-6.0158-6.0158V44.312a6.0158 6.0158 0 0 1 6.0158-6.0158zM31.3642 21.6047c-3.3328 0-6.0162 2.6829-6.0162 6.0157v70.9874c0 3.3328 2.6834 6.0157 6.0162 6.0157H42.7485V44.3119c0-3.3328 2.6829-6.0157 6.0157-6.0157h40.4322V27.6204c0-3.3328-2.6829-6.0157-6.0157-6.0157z",
            onclick: () => copyEChartsToClipboard(chartRef, notifications.show),
          },
        },
      },
      animation: false,
      legend: {
        top: 40,
        left: "right",
      },
      grid: {
        left: 40,
        right: 20,
        bottom: 24,
        top: 75,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: categories,
        name: "Ion Counts",
        nameLocation: "middle",
        nameGap: 32,
        axisLabel: {
          interval: 1,
          hideOverlap: true,
        },
      },
      yAxis: {
        type: "value",
        name: "Count",
        nameLocation: "middle",
        nameGap: 40,
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
  }, [title, categories, seriesData]);

  const empty = !option;

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
          style={{ width: "100%", height: 300 }}
          onChartReady={(chart: ECharts) => {
            chartRef.current = chart;
          }}
        />
      )}
    </>
  );
};

export default HistogramPlot;
