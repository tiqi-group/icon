import React, { useMemo } from "react";
import { ExperimentData } from "../types/ExperimentData";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";

interface ResultChannelPlotProps {
  experimentData: ExperimentData;
  loading: boolean;
}

const formatAxisLabel = (value: string): string => {
  const num = parseFloat(value);
  return isNaN(num) ? value : num.toFixed(3);
};

const ResultChannelPlot = ({ experimentData, loading }: ResultChannelPlotProps) => {
  const option = useMemo<ReactEChartsProps["option"] | undefined>(() => {
    if (!experimentData || Object.keys(experimentData.scan_parameters).length === 0)
      return {};

    const scanParams = Object.entries(experimentData.scan_parameters);
    const scanInfo = scanParams.map(([param, values]) => ({
      parameter_name: param,
      scan_interval: Object.values(values) as string[] | number[],
    }));

    const timestampEntry = scanInfo.find((p) => p.parameter_name === "timestamp");
    const scanParamsOnly = scanInfo.filter((p) => p.parameter_name !== "timestamp");

    const resultChannels = Object.entries(experimentData.result_channels).map(
      ([name, data]) => ({
        name,
        data: Object.values(data),
      }),
    );

    const channelNames = resultChannels.map(({ name }) => name);
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

    if (scanParamsOnly.length === 0 && timestampEntry) {
      xAxis.type = "time";
      xAxis.name = "Time";
      xAxisData = timestampEntry.scan_interval as string[];

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
    } else if (scanParamsOnly.length === 1 && timestampEntry) {
      xAxisData = scanParamsOnly[0].scan_interval as number[];

      xAxis.name = scanParamsOnly[0].parameter_name;
      // @ts-expect-error Type hint of ECharts is wrong
      xAxis.axisLabel = { formatter: formatAxisLabel };

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
        showSymbol: true,
      }));
    } else if (scanParamsOnly.length === 2) {
      const [xScan, yScan] = scanParamsOnly;
      const resultChannel = resultChannels.at(-1);
      if (!resultChannel) return;

      const data: [number | string, number | string, number][] =
        xScan.scan_interval.map((x, i) => [
          x,
          yScan.scan_interval[i],
          resultChannel.data[i],
        ]);

      return {
        tooltip: {},
        xAxis: {
          type: "category",
          axisLabel: { formatter: formatAxisLabel },
          name: xScan.parameter_name,
          nameLocation: "middle",
          nameGap: 25,
        },
        yAxis: {
          type: "category",
          axisLabel: { formatter: formatAxisLabel },
          name: yScan.parameter_name,
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
      textStyle: { fontFamily: "sans-serif", fontSize: 12 },
      tooltip: { trigger: "axis" },
      toolbox: {
        feature: { dataZoom: { yAxisIndex: "none" }, saveAsImage: {} },
      },
      animation: false,
      legend: { data: channelNames },
      grid: {
        left: "8%",
        right: "3%",
        bottom: "12%",
        show: true,
      },
      xAxis,
      yAxis,
      series: chartSeries,
    };
  }, [experimentData]);

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
        <ReactECharts option={option} loading={loading} />
      )}
    </>
  );
};

export default React.memo(ResultChannelPlot);
