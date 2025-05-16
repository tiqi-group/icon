import { useEffect, useMemo, useState } from "react";
import { Box } from "@mui/material";
import { runMethod } from "../socket";
import { ExperimentData } from "../types/ExperimentData";
import { deserialize } from "../utils/deserializer";
import { SerializedObject } from "../types/SerializedObject";
import { ReactECharts, ReactEChartsProps } from "./ReactEcharts";
import { EChartsOption } from "echarts";

interface PlotInterfaceProps {
  jobId: number;
}

const PlotInterface = ({ jobId }: PlotInterfaceProps) => {
  const [experimentData, setExperimentData] = useState<ExperimentData>({
    shot_channels: {},
    result_channels: {},
    vector_channels: {},
    scan_parameters: {},
  });

  useEffect(() => {
    runMethod("data.get_experiment_data_by_job_id", [], { job_id: jobId }, (result) => {
      setExperimentData(deserialize(result as SerializedObject) as ExperimentData);
    });
    // socket.on("", async () => {});
  }, [jobId]);

  const option = useMemo<ReactEChartsProps["option"]>(() => {
    if (!experimentData || Object.keys(experimentData.scan_parameters).length === 0)
      return {};

    const scanParams = Object.entries(experimentData.scan_parameters);
    const scanInfo = scanParams.map(([param, values]) => ({
      parameter_name: param,
      scan_interval: Object.values(values) as string[] | number[],
    }));

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

    // **Handle Time-Based 1D Scans**
    if (scanInfo.length == 1 && scanInfo[0].parameter_name === "timestamp") {
      xAxis["type"] = "time";
      xAxisData = scanInfo[0].scan_interval as string[];

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

      return {
        textStyle: { fontFamily: "sans-serif", fontSize: 12 },
        title: { left: "center", text: `Experiment ${jobId}` },
        tooltip: { trigger: "axis" },
        toolbox: {
          feature: { restore: {}, dataZoom: { yAxisIndex: "none" }, saveAsImage: {} },
        },
        animation: false,
        legend: { data: channelNames, right: "0%", top: "10%" },
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
    } else if (scanInfo.length === 2 && scanInfo[0].parameter_name === "timestamp") {
      xAxisData = scanInfo[1].scan_interval as number[];
      console.log(scanInfo[1].scan_interval);

      console.log(xAxisData);
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

      return {
        textStyle: { fontFamily: "sans-serif", fontSize: 12 },
        title: { left: "center", text: `Experiment ${jobId}` },
        tooltip: { trigger: "axis" },
        toolbox: {
          feature: { restore: {}, dataZoom: { yAxisIndex: "none" }, saveAsImage: {} },
        },
        animation: false,
        legend: { data: channelNames, right: "0%", top: "10%" },
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
    } else if (scanInfo.length === 3) {
      // **Handle 2D Scans (Heatmap)**
      const data: number[][] = [];
      for (let i = 0; i < scanInfo[0].scan_interval.length; i++) {
        for (let j = 0; j < scanInfo[1].scan_interval.length; j++) {
          data.push([
            i,
            j,
            resultChannels[0].data[i + scanInfo[0].scan_interval.length * j],
          ]);
        }
      }

      //@ts-expect-error: bla
      xAxis.data = scanInfo[0].scan_interval as string[];
      //@ts-expect-error: bla
      yAxis.data = scanInfo[1].scan_interval as number[];

      return {
        title: { left: "center", text: `Experiment ${jobId}` },
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
      throw new Error("More than two scanned parameters are not supported.");
    }
  }, [experimentData]);

  return (
    <Box display="flex" sx={{ width: 1, height: 1 }}>
      <ReactECharts option={option} />
    </Box>
  );
};

export default PlotInterface;
