import React, { useMemo } from "react";
import { ExperimentData } from "../types/ExperimentData";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";

interface ResultChannelPlotProps {
  experimentData: ExperimentData;
}

const ResultChannelPlot = ({ experimentData }: ResultChannelPlotProps) => {
  const option = useMemo<ReactEChartsProps["option"]>(() => {
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
      nameGap: 20,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      min: "dataMin",
      max: "dataMax",
      type: "value",
    };
    const yAxis: EChartsOption["yAxis"] = {
      nameLocation: "middle",
      nameGap: 20,
      minorTick: { show: true },
      minorSplitLine: { show: true },
      scale: true,
      boundaryGap: ["1%", "1%"],
    };
    let chartSeries: EChartsOption["series"] = [];

    if (scanParamsOnly.length === 0 && timestampEntry) {
      xAxis.type = "time";
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
      const data: number[][] = [];
      for (let i = 0; i < xScan.scan_interval.length; i++) {
        for (let j = 0; j < yScan.scan_interval.length; j++) {
          data.push([i, j, resultChannels[0].data[i + xScan.scan_interval.length * j]]);
        }
      }

      //@ts-expect-error
      xAxis.data = xScan.scan_interval;
      xAxis.type = "category";
      //@ts-expect-error
      yAxis.data = yScan.scan_interval;
      //@ts-expect-error
      yAxis.type = "category";

      return {
        tooltip: {},
        xAxis,
        yAxis,
        series: [
          {
            name: "Heatmap",
            type: "heatmap",
            data,
            emphasis: { itemStyle: { borderColor: "#333", borderWidth: 1 } },
            progressive: 1000,
            animation: false,
          },
        ],
        visualMap: {
          min: 0,
          max: 1,
          calculable: true,
          realtime: false,
          inRange: { color: ["#313695", "#1483d5", "#73bf7f", "#fcbe3d", "#ffff00"] },
        },
      };
    } else {
      return {};
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
        left: "3%",
        right: "10%",
        bottom: "3%",
        containLabel: true,
        show: true,
      },
      xAxis,
      yAxis,
      series: chartSeries,
    };
  }, [experimentData]);

  return (
    <>
      {Object.keys(experimentData.result_channels).length === 0 ? (
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
      ) : (
        <ReactECharts option={option} />
      )}
    </>
  );
};

export default React.memo(ResultChannelPlot);
