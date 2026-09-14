import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ExperimentData, FitResult } from "../types/ExperimentData";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";
import type { ECharts } from "echarts/core";
import { useNotifications } from "@toolpad/core";
import { ScanParameter } from "../types/ScanParameter";
import {
  CHART_AXIS_NAME,
  CHART_GRID,
  CHART_LEGEND,
  CHART_TEXT_STYLE,
  chartTitle,
  chartToolbox,
} from "../utils/chartLayout";
import { buildResultChannelChartSeries } from "../utils/buildResultChannelChartSeries";

interface ResultChannelPlotProps {
  experimentData: ExperimentData;
  loading: boolean;
  title: string;
  subtitle: string;
  channelNames: string[];
  repetitions: number | undefined;
  showRepetitions: boolean;
  scanParameters: ScanParameter[] | undefined;
  windowSize?: number | null;
  yRange?: { min: number | null; max: number | null };
  fits?: Record<string, FitResult>;
  onChartClick?: (xValue: number) => void;
}

const formatAxisLabel = (value: string): string => {
  const num = parseFloat(value);
  if (isNaN(num)) return value;
  return String(Number(num.toPrecision(6)));
};

function hasDayBreak(data: string[]) {
  const first = new Date(data[0]);
  const last = new Date(data.at(-1) || data[0]);
  return !isNaN(first.getDay()) && first.getDay() != last.getDay();
}

const pad = (value: number) => String(value).padStart(2, "0");

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  const h = pad(date.getHours());
  const m = pad(date.getMinutes());
  const s = pad(date.getSeconds());
  return `${h}:${m}:${s}`;
}

function formatDateTime(timestamp: string) {
  const date = new Date(timestamp);
  const year = date.getFullYear();
  // getMonth() is zero-based
  const month = pad(date.getMonth() + 1);
  const day = pad(date.getDate());
  const time = formatTime(timestamp);
  return `${year}-${month}-${day} ${time}`;
}

function timeAxisProps(data: string[]) {
  return {
    axisLabel: {
      formatter: hasDayBreak(data) ? formatDateTime : formatTime,
    },
  };
}

const ResultChannelPlot = ({
  experimentData,
  loading,
  title: titleText,
  subtitle,
  channelNames,
  repetitions = 1,
  showRepetitions = false,
  scanParameters = [],
  windowSize = null,
  yRange,
  fits = {},
  onChartClick,
}: ResultChannelPlotProps) => {
  const [chart, setChart] = useState<ECharts | null>(null);
  const notifications = useNotifications();

  const [selectedChannel, setSelectedChannel] = useState<string | undefined>(undefined);

  const is2D = scanParameters.length === 2;

  const option = useMemo<ReactEChartsProps["option"] | undefined>(() => {
    if (!experimentData || Object.keys(experimentData.scan_parameters).length === 0)
      return {};

    const scanParams = Object.entries(experimentData.scan_parameters);
    const scanInfo = scanParams.map(([param, values]) => ({
      name: param,
      scanValues: Object.values(values) as string[] | number[],
    }));

    const timestampEntry = scanInfo.find((param) => param.name === "timestamp");

    const resultChannels = Object.entries(experimentData.readouts.result_channels)
      .filter(([name]) => channelNames.includes(name))
      .map(([name, data]) => ({
        name,
        data: Object.values(data),
      }));

    let xAxisData: string[] | number[];
    const xAxis: EChartsOption["xAxis"] = {
      ...CHART_AXIS_NAME,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      min: "dataMin",
      max: "dataMax",
      axisLabel: {
        // hide overlapping labels
        hideOverlap: true,
      },
    };
    const yAxis: EChartsOption["yAxis"] = {
      name: "counts",
      ...CHART_AXIS_NAME,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      scale: true,
      boundaryGap: ["1%", "1%"],
      ...(yRange?.min != null && !(yRange?.max != null && yRange.max <= yRange.min)
        ? { min: yRange.min }
        : {}),
      ...(yRange?.max != null && !(yRange?.min != null && yRange.max <= yRange.min)
        ? { max: yRange.max }
        : {}),
    };
    const title = chartTitle(titleText, subtitle);
    let chartSeries: EChartsOption["series"] = [];
    const nOrdinaryParameters =
      scanParameters.length -
      scanParameters.reduce((total, param) => (param.realtime ? total + 1 : total), 0);

    if (nOrdinaryParameters === 0 && timestampEntry) {
      let tsValues = timestampEntry.scanValues as string[];
      let channels = resultChannels;

      if (windowSize != null && tsValues.length > windowSize) {
        tsValues = tsValues.slice(-windowSize);
        channels = resultChannels.map((ch) => ({
          name: ch.name,
          data: ch.data.slice(-windowSize),
        }));
      }

      xAxisData = tsValues;
      Object.assign(xAxis, { type: "time", name: "Time", ...timeAxisProps(xAxisData) });

      const fullDataSet = xAxisData.map((xVal, index) => [
        xVal,
        ...channels.map((ch) => ch.data[index]),
      ]);

      chartSeries = channels.map((channel, index) => ({
        name: channel.name,
        type: "line",
        clip: true,
        sampling: "lttb",
        encode: { x: 0, y: index + 1 },
        data: fullDataSet,
        showSymbol: false,
      }));
    } else if (scanParameters.length === 1) {
      xAxis.type = "value";
      xAxis.name = scanParameters[0].name;
      xAxis.axisLabel = { formatter: formatAxisLabel };

      const ordinaryScanEntry = scanInfo.find((param) => param.name !== "timestamp");

      if (
        windowSize != null &&
        ordinaryScanEntry &&
        resultChannels[0]?.data.length > windowSize
      ) {
        const observedX = (ordinaryScanEntry.scanValues as number[]).slice(-windowSize);
        const channels = resultChannels.map((ch) => ({
          name: ch.name,
          data: ch.data.slice(-windowSize),
        }));

        xAxisData = observedX;

        const fullDataSet = observedX
          .map((xVal, index) => [xVal, ...channels.map((ch) => ch.data[index])])
          .sort((a, b) => (a[0] as number) - (b[0] as number));

        chartSeries = channels.map((channel, index) => ({
          name: channel.name,
          type: "line",
          clip: true,
          sampling: "lttb",
          encode: { x: 0, y: index + 1 },
          data: fullDataSet,
          showSymbol: true,
          lineStyle: { width: 2 },
        }));
      } else {
        xAxisData = scanParameters[0].scan_values;

        chartSeries = buildResultChannelChartSeries(
          xAxisData,
          resultChannels,
          repetitions,
          showRepetitions,
        );
      }
    } else if (scanParameters.length === 2) {
      const [xScan, yScan] = scanParameters;
      const xScanValues =
        xScan.realtime && timestampEntry
          ? timestampEntry.scanValues
          : xScan.scan_values;
      const yScanValues =
        yScan.realtime && timestampEntry
          ? timestampEntry.scanValues
          : yScan.scan_values;
      const series = [];

      const xCategories = xScan.realtime
        ? undefined
        : [...new Set(xScanValues as number[])]
            .sort((a, b) => a - b)
            .map((v) => String(v));
      const yCategories = yScan.realtime
        ? undefined
        : [...new Set(yScanValues as number[])]
            .sort((a, b) => a - b)
            .map((v) => String(v));

      for (const resultChannel of resultChannels) {
        const data: [number | string, number | string, number][] = [];
        if (xScan.realtime) {
          for (let i = 0; i < xScanValues.length; i++) {
            data.push([
              xScanValues[Math.floor(i / yScanValues.length)],
              String(yScanValues[i % yScanValues.length]),
              resultChannel.data[i],
            ]);
          }
        } else if (yScan.realtime) {
          for (let i = 0; i < yScanValues.length; i++) {
            data.push([
              String(xScanValues[i % xScanValues.length]),
              yScanValues[Math.floor(i / xScanValues.length)],
              resultChannel.data[i],
            ]);
          }
        } else {
          for (let i = 0; i < xScanValues.length; i++) {
            for (let j = 0; j < yScanValues.length; j++) {
              data.push([
                String(xScanValues[i]),
                String(yScanValues[j]),
                resultChannel.data[i * yScanValues.length + j],
              ]);
            }
          }
        }

        series.push({
          name: resultChannel.name,
          type: "heatmap",
          data,
          emphasis: { itemStyle: { borderColor: "#333", borderWidth: 1 } },
          animation: false,
        });
      }

      // Determine which channel is currently displayed and compute its data range so
      // the color bar always reflects the actual values without a post-render fixup.
      const activeChannelName = selectedChannel ?? resultChannels[0]?.name;
      const activeChannel =
        resultChannels.find((rc) => rc.name === activeChannelName) ?? resultChannels[0];
      const finiteValues = (activeChannel?.data ?? []).filter((v) =>
        Number.isFinite(v),
      );
      const vmMin = finiteValues.length ? Math.min(...finiteValues) : 0;
      const vmMax =
        finiteValues.length && Math.max(...finiteValues) !== vmMin
          ? Math.max(...finiteValues)
          : vmMin + 1; // guard against a flat / empty dataset

      // Preserve the legend selection across setOption({ notMerge: true }) calls.
      const legendSelected = Object.fromEntries(
        resultChannels.map((rc) => [rc.name, rc.name === activeChannelName]),
      );

      const categoryAxisProps = {
        axisLabel: { formatter: formatAxisLabel },
      };

      return {
        title,
        textStyle: CHART_TEXT_STYLE,
        toolbox: chartToolbox(chart, notifications.show),
        legend: {
          ...CHART_LEGEND,
          selectedMode: "single",
          selected: legendSelected,
        },
        // leave room on the right for the colour bar and its labels
        grid: { ...CHART_GRID, right: 88 },
        tooltip: {
          trigger: "item",
          formatter: (params: {
            seriesName?: string;
            value: [number | string, number | string, number];
          }) => {
            const [x, y, value] = params.value;
            return [
              xScan.realtime
                ? formatDateTime(String(x))
                : yScan.realtime
                  ? formatDateTime(String(y))
                  : undefined,
              xScan.realtime
                ? undefined
                : `${xScan.name}: ${formatAxisLabel(String(x))}`,
              yScan.realtime
                ? undefined
                : `${yScan.name}: ${formatAxisLabel(String(y))}`,
              `${params.seriesName}: <b>${value}</b>`,
            ]
              .filter(Boolean)
              .join("<br/>");
          },
        },
        xAxis: {
          name: xScan.name,
          type: "category",
          ...CHART_AXIS_NAME,
          ...(xCategories ? { data: xCategories } : {}),
          ...(xScan.realtime
            ? timeAxisProps(xScanValues as string[])
            : categoryAxisProps),
        },
        yAxis: {
          name: yScan.name,
          type: "category",
          ...CHART_AXIS_NAME,
          ...(yCategories ? { data: yCategories } : {}),
          ...(yScan.realtime
            ? timeAxisProps(yScanValues as string[])
            : categoryAxisProps),
        },
        series,
        visualMap: [
          {
            type: "continuous",
            show: true,
            calculable: true,
            orient: "vertical",
            right: 8,
            top: "middle",
            itemWidth: 14,
            textStyle: { fontSize: 11 },
            min: vmMin,
            max: vmMax,
            inRange: { color: ["#313695", "#1483d5", "#73bf7f", "#fcbe3d", "#ffff00"] },
          },
        ],
      };
    }

    // Add fit curve overlays for 1D scans
    if (scanParameters.length === 1 && fits) {
      for (const [channelName, fitResult] of Object.entries(fits)) {
        if (!fitResult.success || !fitResult.fit_curve) continue;
        if (!channelNames.includes(channelName)) continue;

        const fitData = fitResult.fit_curve.x.map((x, i) => [
          x,
          fitResult.fit_curve!.y[i],
        ]);

        (chartSeries as unknown[]).push({
          name: `${channelName} fit`,
          type: "line",
          data: fitData,
          showSymbol: false,
          lineStyle: { type: "dashed", width: 2 },
          tooltip: { show: false },
        });
      }
    }

    return {
      title,
      textStyle: CHART_TEXT_STYLE,
      tooltip: { trigger: "axis" },
      toolbox: chartToolbox(chart, notifications.show),
      animation: false,
      legend: CHART_LEGEND,
      grid: CHART_GRID,
      xAxis,
      yAxis,
      series: chartSeries,
    };
  }, [
    experimentData,
    titleText,
    subtitle,
    scanParameters,
    repetitions,
    showRepetitions,
    windowSize,
    yRange,
    fits,
    channelNames,
    selectedChannel,
    chart,
    notifications.show,
  ]);

  const updateChart = useCallback(
    (chart: ECharts) => {
      setChart(chart);
    },
    [setChart],
  );

  useEffect(() => {
    if (!chart || !onChartClick) return;
    const zr = chart.getZr();
    const handler = (params: { offsetX: number; offsetY: number }) => {
      const point = [params.offsetX, params.offsetY];
      if (chart.containPixel("grid", point)) {
        const dataPoint = chart.convertFromPixel("grid", point);
        if (dataPoint && typeof dataPoint[0] === "number" && isFinite(dataPoint[0])) {
          onChartClick(dataPoint[0]);
        }
      }
    };
    zr.on("click", handler);
    return () => {
      zr.off("click", handler);
    };
  }, [chart, onChartClick]);

  // When the user picks a different channel in the legend, update selectedChannel so
  // the useMemo recomputes the option (including the correct visualMap range) for the
  // newly active channel.
  useEffect(() => {
    if (!is2D || !chart) return;

    // @ts-expect-error Typing is incorrect
    chart.on("legendselectchanged", (e: { name: string }) => {
      setSelectedChannel(e.name);
    });

    return () => {
      chart.off("legendselectchanged");
    };
  }, [chart, is2D]);

  return (
    <>
      {Object.keys(experimentData.readouts.result_channels).length === 0 ||
      option === undefined ? (
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
            No result data available.
          </div>
        )
      ) : (
        <ReactECharts option={option} loading={loading} onChartReady={updateChart} />
      )}
    </>
  );
};

export default React.memo(ResultChannelPlot);
