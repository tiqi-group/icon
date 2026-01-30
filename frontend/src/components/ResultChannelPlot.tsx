import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ExperimentData } from "../types/ExperimentData";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";
import type { ECharts } from "echarts/core";
import { useNotifications } from "@toolpad/core";
import { copyEChartsToClipboard } from "../utils/copyEChartsToClipboard";
import { ScanParameter } from "../types/ScanParameter";
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
}

const formatAxisLabel = (value: string): string => {
  const num = parseFloat(value);
  return isNaN(num) ? value : num.toFixed(3);
};

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

function updateVisualMap(chart: ECharts, selectedChannelName: string | undefined) {
  const opt = chart.getOption();

  if (!selectedChannelName)
    selectedChannelName = Object.entries(
      // @ts-expect-error Type hint of ECharts is wrong
      opt.legend[0].selected as Record<string, boolean>,
    ).find(([, v]) => v)?.[0];

  // @ts-expect-error Type hint of ECharts is wrong
  const s = opt.series.find((ss) => ss.name === selectedChannelName);
  if (!s || !s.data) return;

  const channelValues = (s.data as [number, number, number][])
    .map((d) => d[2])
    .filter((v: number) => Number.isFinite(v));

  if (!channelValues.length) return;

  const min = Math.min(...channelValues);
  const max = Math.max(...channelValues);

  chart.dispatchAction({
    type: "legendSelect",
    name: selectedChannelName,
  });

  chart.setOption({
    visualMap: [{ min, max }],
  });
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

    const resultChannels = Object.entries(experimentData.result_channels)
      .filter(([name]) => channelNames.includes(name))
      .map(([name, data]) => ({
        name,
        data: Object.values(data),
      }));

    let xAxisData: string[] | number[];
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
    const yAxis: EChartsOption["yAxis"] = {
      name: "counts",
      nameLocation: "middle",
      nameGap: 35,
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
      xAxis.name = scanParameters[0].variable_id;
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

        const fullDataSet = observedX.map((xVal, index) => [
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

      const categoryAxisProps = {
        axisLabel: { formatter: formatAxisLabel },
      };

      return {
        title,
        legend: {
          selectedMode: "single",
          left: "right",
          top: 40,
        },
        grid: {
          left: 30,
          right: 40,
          bottom: 20,
          top: 70,
          containLabel: true,
        },
        tooltip: {},
        xAxis: {
          name: xScan.variable_id,
          type: "category",
          nameLocation: "middle",
          nameGap: 25,
          ...(xScan.realtime
            ? timeAxisProps(xScanValues as string[])
            : categoryAxisProps),
        },
        yAxis: {
          name: yScan.variable_id,
          type: "category",
          nameLocation: "middle",
          nameGap: 45,
          ...(yScan.realtime
            ? timeAxisProps(yScanValues as string[])
            : categoryAxisProps),
        },
        series,
        visualMap: {
          left: "right",
          bottom: 30,
          inRange: { color: ["#313695", "#1483d5", "#73bf7f", "#fcbe3d", "#ffff00"] },
        },
      };
    }

    return {
      title,
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
    repetitions,
    showRepetitions,
    windowSize,
    yRange,
  ]);

  const updateChart = useCallback(
    (chart: ECharts) => {
      setChart(chart);
    },
    [setChart],
  );

  useEffect(() => {
    if (!is2D || !chart) return;

    updateVisualMap(chart, selectedChannel);
  }, [option, chart]);

  useEffect(() => {
    if (!is2D || !chart) return;

    // @ts-expect-error Typing is incorrect
    chart.on("legendselectchanged", (e: { name: string }) => {
      setSelectedChannel(e.name);
      updateVisualMap(chart, e.name);
    });

    return () => {
      chart.off("legendselectchanged");
    };
  }, [chart]);

  return (
    <>
      {Object.keys(experimentData.result_channels).length === 0 ||
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
