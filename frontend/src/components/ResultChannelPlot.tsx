import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ExperimentData, FitResult } from "../types/ExperimentData";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";
import type { ECharts } from "echarts/core";
import { useNotifications } from "@toolpad/core";
import { copyEChartsToClipboard } from "../utils/copyEChartsToClipboard";
import { ScanParameter } from "../types/ScanParameter";
import { ExperimentMetadata } from "../types/ExperimentMetadata";
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
  numberOfShots?: number;
  experimentMetadata?: ExperimentMetadata | null;
  windowSize?: number | null;
  yRange?: { min: number | null; max: number | null };
  fits?: Record<string, FitResult>;
  onChartClick?: (xValue: number) => void;
}

function yDecimalsFromShots(shots: number, repetitions: number): number {
  const n = Math.max(1, shots) * Math.max(1, repetitions);
  return n <= 1 ? 0 : Math.ceil(Math.log10(n));
}

function xDecimalsFromValues(values: number[]): number {
  const nums = [...new Set(values.filter(Number.isFinite))].sort((a, b) => a - b);
  if (nums.length < 2) return 0;
  let step = Infinity;
  for (let i = 1; i < nums.length; i++) {
    const delta = nums[i] - nums[i - 1];
    if (delta > 0) step = Math.min(step, delta);
  }
  if (!Number.isFinite(step) || step >= 1) return 0;
  for (let d = 0; d <= 12; d++) {
    const factor = 10 ** d;
    if (Math.abs(Math.round(step * factor) / factor - step) < step * 1e-10 + 1e-12) {
      return d;
    }
  }
  return 12;
}

function formatNum(value: unknown, decimals: number): string {
  const num = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(num)) return String(value ?? "");
  return Number(num.toFixed(decimals)).toString();
}

function axisName(
  param: ScanParameter,
  metadata?: ExperimentMetadata | null,
): string {
  const unit =
    param.unit?.trim() ||
    Object.values(metadata?.parameters ?? {}).find((group) => group[param.variable_id])?.[
      param.variable_id
    ]?.unit;
  return unit ? `${param.name} (${unit})` : param.name;
}

function hasDayBreak(data: string[]) {
  const first = new Date(data[0]);
  const last = new Date(data.at(-1) || data[0]);
  return !isNaN(first.getDay()) && first.getDay() != last.getDay();
}

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  const h = date.getHours();
  const m = date.getMinutes();
  const s = date.getSeconds();
  return `${h}:${m}:${s}`;
}

function formatDateTime(timestamp: string) {
  const date = new Date(timestamp);
  const year = date.getFullYear();
  const month = date.getMonth();
  const day = date.getDate();
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
  numberOfShots = 50,
  experimentMetadata = null,
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
    let isTimeAxis = false;
    const xAxis: EChartsOption["xAxis"] = {
      nameLocation: "middle",
      nameGap: 25,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      min: "dataMin",
      max: "dataMax",
      axisLabel: {
        // hide overlapping labels
        hideOverlap: true,
      },
    };
    const yDecimals = yDecimalsFromShots(numberOfShots, repetitions);
    let xDecimals = xDecimalsFromValues(
      scanParameters.flatMap((param) => (param.realtime ? [] : param.scan_values)),
    );

    const yAxis: EChartsOption["yAxis"] = {
      name: "counts",
      nameLocation: "middle",
      nameGap: 35,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      scale: true,
      boundaryGap: ["1%", "1%"],
      axisLabel: {
        formatter: (value: string | number) => formatNum(value, yDecimals),
      },
      ...(yRange?.min != null && !(yRange?.max != null && yRange.max <= yRange.min)
        ? { min: yRange.min }
        : {}),
      ...(yRange?.max != null && !(yRange?.min != null && yRange.max <= yRange.min)
        ? { max: yRange.max }
        : {}),
    };
    const title = {
      text: titleText,
      left: "center",
      subtext: subtitle,
      subtextStyle: {
        lineHeight: 0,
      },
      top: "-1%",
    };
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
      isTimeAxis = true;
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
      xAxis.name = axisName(scanParameters[0], experimentMetadata);
      xDecimals = xDecimalsFromValues(scanParameters[0].scan_values);
      xAxis.axisLabel = {
        hideOverlap: true,
        formatter: (value: string | number) => formatNum(value, xDecimals),
      };

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

      for (const resultChannel of resultChannels) {
        const data: [number | string, number | string, number][] = [];
        if (xScan.realtime) {
          for (let i = 0; i < xScanValues.length; i++) {
            data.push([
              xScanValues[Math.floor(i / yScanValues.length)],
              yScanValues[i % yScanValues.length],
              resultChannel.data[i],
            ]);
          }
        } else if (yScan.realtime) {
          for (let i = 0; i < yScanValues.length; i++) {
            data.push([
              xScanValues[i % xScanValues.length],
              yScanValues[Math.floor(i / xScanValues.length)],
              resultChannel.data[i],
            ]);
          }
        } else {
          for (let i = 0; i < xScanValues.length; i++) {
            for (let j = 0; j < yScanValues.length; j++) {
              data.push([
                xScanValues[i],
                yScanValues[j],
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

      const xScanDecimals = xScan.realtime ? 0 : xDecimalsFromValues(xScan.scan_values);
      const yScanDecimals = yScan.realtime ? 0 : xDecimalsFromValues(yScan.scan_values);
      const xAxisTitle = axisName(xScan, experimentMetadata);
      const yAxisTitle = axisName(yScan, experimentMetadata);
      const categoryAxisProps = (decimals: number) => ({
        axisLabel: {
          formatter: (value: string | number) => formatNum(value, decimals),
        },
      });

      return {
        title,
        legend: {
          selectedMode: "single",
          top: 40,
          left: "center",
          selected: legendSelected,
        },
        grid: {
          left: 30,
          right: 160,
          bottom: 20,
          top: 70,
          containLabel: true,
        },
        tooltip: {
          formatter: (param: { value?: unknown; seriesName?: string }) => {
            const value = param.value;
            if (!Array.isArray(value) || value.length < 3) return "";
            return [
              `${xAxisTitle}: ${formatNum(value[0], xScanDecimals)}`,
              `${yAxisTitle}: ${formatNum(value[1], yScanDecimals)}`,
              `${param.seriesName ?? ""}: ${formatNum(value[2], yDecimals)}`,
            ].join("<br/>");
          },
        },
        xAxis: {
          name: xAxisTitle,
          type: "category",
          nameLocation: "middle",
          nameGap: 25,
          ...(xScan.realtime
            ? timeAxisProps(xScanValues as string[])
            : categoryAxisProps(xScanDecimals)),
        },
        yAxis: {
          name: yAxisTitle,
          type: "category",
          nameLocation: "middle",
          nameGap: 45,
          ...(yScan.realtime
            ? timeAxisProps(yScanValues as string[])
            : categoryAxisProps(yScanDecimals)),
        },
        series,
        visualMap: [
          {
            type: "continuous",
            show: true,
            calculable: true,
            orient: "vertical",
            right: 10,
            top: "center",
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
      textStyle: { fontFamily: "sans-serif", fontSize: 12 },
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const items = (Array.isArray(params) ? params : [params]) as {
            marker?: string;
            seriesName?: string;
            value?: unknown;
            axisValue?: unknown;
            encode?: { y?: number | number[] };
          }[];
          if (items.length === 0) return "";
          const first = items[0];
          const xRaw = Array.isArray(first.value) ? first.value[0] : first.axisValue;
          const header = isTimeAxis ? String(xRaw ?? "") : formatNum(xRaw, xDecimals);
          return [
            header,
            ...items.map((item) => {
              const yEnc = item.encode?.y;
              const yIdx = Array.isArray(yEnc) ? (yEnc[0] ?? 1) : (yEnc ?? 1);
              const y = Array.isArray(item.value) ? item.value[yIdx] : item.value;
              return `${item.marker ?? ""}${item.seriesName ?? ""}: ${formatNum(y, yDecimals)}`;
            }),
          ].join("<br/>");
        },
      },
      toolbox: {
        top: -6,
        feature: {
          dataZoom: { yAxisIndex: "none" },
          myCopyToClipboard: {
            show: true,
            title: "Copy to Clipboard",
            icon: "path://M48.7643 38.2962H100.5807a6.0158 6.0158 0 0 1 6.0158 6.0158V115.2992a6.0158 6.0158 0 0 1-6.0158 6.0158H48.7643a6.0158 6.0158 0 0 1-6.0158-6.0158V44.312a6.0158 6.0158 0 0 1 6.0158-6.0158zM31.3642 21.6047c-3.3328 0-6.0162 2.6829-6.0162 6.0157v70.9874c0 3.3328 2.6834 6.0157 6.0162 6.0157H42.7485V44.3119c0-3.3328 2.6829-6.0157 6.0157-6.0157h40.4322V27.6204c0-3.3328-2.6829-6.0157-6.0157-6.0157z",
            onclick: () => copyEChartsToClipboard(chart, notifications.show),
          },
        },
      },
      animation: false,
      legend: {
        top: 40,
        left: "right",
      },
      grid: {
        left: 30,
        right: 20,
        bottom: 20,
        top: 75,
        containLabel: true,
      },
      xAxis,
      yAxis,
      series: chartSeries,
    };
  }, [
    experimentData,
    titleText,
    subtitle,
    scanParameters,
    numberOfShots,
    experimentMetadata,
    repetitions,
    showRepetitions,
    windowSize,
    yRange,
    fits,
    channelNames,
    selectedChannel,
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
