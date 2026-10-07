import { useCallback, useMemo, useRef, useState } from "react";
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

const MAX_BINS = 50;
const BINS_PER_LABEL = 5;

interface Histogram {
  /** Lower edge of the first bin, a multiple of BINS_PER_LABEL * binWidth. */
  xMin: number;
  /** Upper edge of the last bin, a multiple of BINS_PER_LABEL * binWidth. */
  xMax: number;
  /** Upper limit of the y-axis, rounded up to a multiple of a 1-2-5 step. */
  yMax: number;
  /** One of 1, 2, 5, 10, 20, 50, ... */
  binWidth: number;
  /** Category label of every bin: the value for a width of 1, else "from–to". */
  categories: string[];
  series: { name: string; data: number[] }[];
}

const niceCeil = (value: number): number => {
  if (value <= 1) return 1;
  const magnitude = 10 ** Math.floor(Math.log10(value));
  for (const step of [1, 2, 5]) {
    if (step * magnitude >= value) return step * magnitude;
  }
  return 10 * magnitude;
};

function buildHistogram(
  channels: Record<string, number[]>,
  previous: Histogram | undefined,
): Histogram | undefined {
  let min = Infinity;
  let max = -Infinity;
  for (const values of Object.values(channels)) {
    for (const v of values) {
      if (!Number.isFinite(v)) continue;
      if (v < min) min = v;
      if (v > max) max = v;
    }
  }
  if (min > max && !previous) return undefined;

  // Without data, min and max are infinite and the previous limits are kept.
  // Widen the bins until the padded and rounded range fits into MAX_BINS.
  let binWidth = Math.max(previous?.binWidth ?? 1, niceCeil((max - min) / MAX_BINS));
  let xMin: number, xMax: number, binCount: number;
  for (;;) {
    const labelStep = BINS_PER_LABEL * binWidth;
    const lower = Math.floor(min / binWidth) * binWidth - binWidth;
    const upper = Math.floor(max / binWidth) * binWidth + 2 * binWidth;
    xMin =
      Math.floor(Math.min(previous?.xMin ?? Infinity, lower) / labelStep) * labelStep;
    xMax =
      Math.ceil(Math.max(previous?.xMax ?? -Infinity, upper) / labelStep) * labelStep;
    binCount = Math.round((xMax - xMin) / binWidth);
    if (binCount <= MAX_BINS) break;
    binWidth = niceCeil(binWidth * 1.5);
  }

  const categories = Array.from({ length: binCount }, (_, i) => {
    const from = xMin + i * binWidth;
    return binWidth === 1 ? String(from) : `${from}–${from + binWidth - 1}`;
  });

  let maxCount = previous?.yMax ?? 0;
  const series = Object.entries(channels).map(([name, values]) => {
    const data = new Array<number>(binCount).fill(0);
    for (const v of values) {
      if (Number.isFinite(v)) data[Math.floor((v - xMin) / binWidth)]++;
    }
    maxCount = Math.max(maxCount, ...data);
    return { name, data };
  });
  // Round up so that the top of the y-axis gets a tick label
  const yStep = niceCeil(maxCount / 5);
  const yMax = Math.ceil(maxCount / yStep) * yStep;

  return { xMin, xMax, yMax, binWidth, categories, series };
}

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

  // Take main device for now:
  const sc = experimentData?.device_data?.[0]?.readouts?.shot_channels;

  const previous = useRef<Histogram | undefined>(undefined);

  const histogram = useMemo(() => {
    const latestPerChannel: Record<string, number[]> = {};
    for (const [channelName, groups] of Object.entries(sc ?? {})) {
      if (!groups || !channelNames.includes(channelName)) continue;

      // Get the latest key by calculating the max of the available keys
      const keys = Object.keys(groups).map(Number);
      const latestKey = String(Math.max(...keys));

      latestPerChannel[channelName] = groups[latestKey];
    }
    previous.current = buildHistogram(latestPerChannel, previous.current);
    return previous.current;
  }, [sc, channelNames]);

  const option = useMemo<EChartsOption | undefined>(() => {
    if (!histogram) return undefined;
    const { xMin, yMax, binWidth, categories, series } = histogram;

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
          // xMin is a multiple of the label step, so these are round values
          interval: (index: number) => index % BINS_PER_LABEL === 0,
          formatter: (_: string, index: number) => String(xMin + index * binWidth),
          hideOverlap: true,
        },
      },
      yAxis: {
        type: "value",
        name: "Count",
        max: yMax,
        ...CHART_AXIS_NAME,
      },
      dataZoom: [
        {
          type: "inside",
          xAxisIndex: 0,
        },
      ],
      series: series.map((s) => ({
        type: "bar",
        name: s.name,
        data: s.data,
        barMaxWidth: 22,
        emphasis: { focus: "series" },
        large: true,
      })),
    };
  }, [title, subtitle, histogram, chart, notifications.show]);

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
