import React, { useMemo, useRef } from "react";
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
}

const formatAxisLabel = (value: string): string => {
  const num = parseFloat(value);
  return isNaN(num) ? value : num.toFixed(3);
};

const ResultChannelPlot = ({
  experimentData,
  loading,
  title,
  subtitle,
  channelNames,
  repetitions = 1,
  showRepetitions = false,
  scanParameters = [],
}: ResultChannelPlotProps) => {
  const chartRef = useRef<ECharts | null>(null);
  const notifications = useNotifications();

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
      type: "value",
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
    };
    let chartSeries: EChartsOption["series"] = [];

    if (scanParameters.length === 0 && timestampEntry) {
      xAxis.type = "time";
      xAxis.name = "Time";
      xAxisData = timestampEntry.scanValues as string[];

      const fullDataSet = xAxisData.map((xVal, index) => [
        xVal,
        ...resultChannels.map((ch) => ch.data[index]),
      ]);

      chartSeries = resultChannels.map((channel, index) => ({
        name: channel.name,
        type: "line",
        clip: true,
        sampling: "lttb",
        encode: { x: 0, y: index + 1 },
        data: fullDataSet,
        showSymbol: false,
      }));
    } else if (scanParameters.length === 1) {
      xAxisData = scanParameters[0].scan_values;

      xAxis.name = scanParameters[0].variable_id;
      // @ts-expect-error Type hint of ECharts is wrong
      xAxis.axisLabel = { formatter: formatAxisLabel };

      chartSeries = buildResultChannelChartSeries(
        xAxisData,
        resultChannels,
        repetitions,
        showRepetitions,
      );
    } else if (scanParameters.length === 2) {
      const [xScan, yScan] = scanParameters;
      const resultChannel = resultChannels.at(-1);
      if (!resultChannel) return;

      const data: [number | string, number | string, number][] = [];
      for (let i = 0; i < xScan.scan_values.length; i++) {
        for (let j = 0; j < yScan.scan_values.length; j++) {
          data.push([
            xScan.scan_values[i],
            yScan.scan_values[j],
            resultChannel.data[i * yScan.scan_values.length + j],
          ]);
        }
      }

      return {
        tooltip: {},
        xAxis: {
          type: "category",
          axisLabel: { formatter: formatAxisLabel },
          name: xScan.variable_id,
          nameLocation: "middle",
          nameGap: 25,
        },
        yAxis: {
          type: "category",
          axisLabel: { formatter: formatAxisLabel },
          name: yScan.variable_id,
          nameLocation: "middle",
          nameGap: 45,
        },
        series: [
          {
            name: resultChannel.name,
            type: "heatmap",
            data,
            emphasis: { itemStyle: { borderColor: "#333", borderWidth: 1 } },
            progressive: 1000,
            animation: false,
          },
        ],
        visualMap: {
          left: "right",
          min: Math.min(...resultChannel.data),
          max: Math.max(1, ...resultChannel.data),
          inRange: { color: ["#313695", "#1483d5", "#73bf7f", "#fcbe3d", "#ffff00"] },
        },
      };
    }

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
  }, [experimentData, title, subtitle, scanParameters, repetitions, showRepetitions]);

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
        <ReactECharts
          option={option}
          loading={loading}
          onChartReady={(chart: ECharts) => {
            chartRef.current = chart;
          }}
        />
      )}
    </>
  );
};

export default React.memo(ResultChannelPlot);
