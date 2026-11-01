import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import HistogramPlot from "../../../src/components/jobView/HistogramPlot";
import type { ReactEChartsProps } from "../../../src/components/ReactEcharts";
import type { ExperimentDataPoint } from "../../../src/types/ExperimentData";
import {
  applyPlotViewerUpdate,
  retainPlotViewerData,
} from "../../../src/features/plot-viewer/plotViewerData";
import type { PlotViewerData } from "../../../src/features/plot-viewer/plotViewerData";
import { projectPlotData } from "../../../src/features/plot-viewer/plotSelection";

jest.mock("../../../src/components/ReactEcharts", () => ({ ReactECharts: () => null }));
jest.mock("@toolpad/core", () => ({ useNotifications: () => ({ show: jest.fn() }) }));

function snapshot(): PlotViewerData {
  return {
    device_data: [
      {
        device_id: "d",
        readouts: {
          result_channels: {},
          shot_channels: { counts: { 9: [1], 100: [2, 2, 3] }, other: { 100: [99] } },
        },
        plot_windows: { result_channels: [], shot_channels: [] },
        fits: {},
      },
    ],
    scan_parameters: {},
    parameters: {},
    total_data_points: 101,
  };
}

function renderHistogram(data: PlotViewerData) {
  const projected = projectPlotData(data, data.device_data[0], ["counts"]);
  let option: ReactEChartsProps["option"];
  function CaptureChart(props: ReactEChartsProps) {
    option = props.option;
    return <div>Histogram rendered</div>;
  }
  const markup = renderToStaticMarkup(
    createElement(HistogramPlot, {
      experimentData: projected,
      channelNames: ["counts"],
      title: "Latest acquired point",
      subtitle: "",
      loading: false,
      ChartComponent: CaptureChart,
    }),
  );
  return { projected, markup, option: option! };
}

test("renders a saved indexed snapshot through the actual shared histogram", () => {
  const data = snapshot();
  const before = JSON.stringify(data);
  const { projected, markup, option } = renderHistogram(data);
  expect(markup).toContain("Histogram rendered");
  expect(projected.device_data[0].readouts.shot_channels).toEqual({
    counts: [2, 2, 3],
  });
  const series = option.series as { name: string; data: number[] }[];
  expect(series.map(({ name }) => name)).toEqual(["counts"]);
  expect(series[0].data.reduce((sum, count) => sum + count, 0)).toBe(3);
  expect(JSON.stringify(data)).toBe(before);
});

test("live and late events preserve latest shots while the held snapshot stays unchanged", () => {
  const held = retainPlotViewerData(snapshot());
  const point = (index: number, shots: number[]): ExperimentDataPoint => ({
    index,
    scan_params: {},
    timestamp: String(index),
    device_data: [
      {
        device_id: "d",
        hardware_instructions: "",
        readouts: {
          result_channels: {},
          shot_channels: { counts: shots },
          vector_channels: {},
        },
      },
    ],
  });
  const live = applyPlotViewerUpdate(held, {
    type: "point",
    value: point(101, [4, 5]),
  });
  const late = applyPlotViewerUpdate(live, { type: "point", value: point(10, [99]) });
  expect(
    renderHistogram(late).projected.device_data[0].readouts.shot_channels.counts,
  ).toEqual([4, 5]);
  expect(
    renderHistogram(held).projected.device_data[0].readouts.shot_channels.counts,
  ).toEqual([2, 2, 3]);
});

test("selects numeric maximum beyond array-index keys and keeps an empty latest shot array", () => {
  const data = snapshot();
  data.device_data[0].readouts.shot_channels.counts = {
    "4294967297": [],
    "4294967296": [7],
    bad: [8],
    "-1": [9],
  };
  const { projected, markup } = renderHistogram(data);
  expect(projected.device_data[0].readouts.shot_channels.counts).toEqual([]);
  expect(markup).toContain("No data.");
});

test("renders a large shot array without spreading it into function arguments", () => {
  const data = snapshot();
  data.device_data[0].readouts.shot_channels.counts = { 1: Array(200_000).fill(3) };
  const { option } = renderHistogram(data);
  const series = option.series as { data: number[] }[];
  expect(series[0].data.reduce((sum, count) => sum + count, 0)).toBe(200_000);
});
