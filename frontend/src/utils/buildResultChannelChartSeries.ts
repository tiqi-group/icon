import { EChartsOption } from "echarts";

interface Channel {
  name: string;
  data: number[];
}

/**
 * Build chart series for result channels with optional repetition traces.
 *
 * - Computes a merged dataset by averaging all repetitions for each channel.
 * - Always creates one "merged" series per channel (coloured from the palette).
 * - Optionally creates one series per channel per repetition (if `showRepetitions` is
 *   true). These repetition series are appended after the merged series and drawn in
 *   lower opacity.
 *
 * @param xAxisData - Array of x-values (scan points).
 * @param resultChannels - Array of channel objects { name, data }. Each channel's
 *   `data` is a flat array of values across all repetitions.
 * @param repetitions - Number of experiment repetitions (used to slice channel data).
 * @param showRepetitions - If true, adds individual traces for each repetition.
 * @param palette - Colour palette for merged channels.
 * @returns EChartsOption["series"] - Series configuration for ECharts.
 */
export function buildResultChannelChartSeries(
  xAxisData: number[],
  resultChannels: Channel[],
  repetitions: number,
  showRepetitions: boolean,
  palette: string[] = ["#37A2DA", "#ffd85c", "#fd7b5f"],
): EChartsOption["series"] {
  const xLen = xAxisData.length;
  const getVal = (ch: Channel, rep: number, i: number): number =>
    Number.isFinite(ch.data[rep * xLen + i]) ? ch.data[rep * xLen + i] : Number.NaN;

  // merged data
  const fullDataSet: number[][] = xAxisData.map((x, i) => {
    const ys = resultChannels.map((ch) => {
      let sum = 0,
        cnt = 0;
      for (let r = 0; r < repetitions; r++) {
        const v = getVal(ch, r, i);
        if (Number.isFinite(v)) {
          sum += v;
          cnt++;
        }
      }
      return cnt ? sum / cnt : Number.NaN;
    });
    return [x, ...ys];
  });

  // merged series with explicit colours from palette
  const chartSeries: EChartsOption["series"] = resultChannels.map((ch, chIdx) => ({
    name: ch.name,
    type: "line",
    clip: true,
    sampling: "lttb",
    encode: { x: 0, y: chIdx + 1 },
    data: fullDataSet,
    showSymbol: true,
    lineStyle: { width: 2 },
    itemStyle: { color: palette[chIdx % palette.length] },
  }));

  if (showRepetitions && repetitions > 1) {
    for (let r = 0; r < repetitions; r++) {
      const repData: number[][] = xAxisData.map((x, i) => {
        const ys = resultChannels.map((ch) => {
          const v = getVal(ch, r, i);
          return Number.isFinite(v) ? v : Number.NaN;
        });
        return [x, ...ys];
      });

      for (let chIdx = 0; chIdx < resultChannels.length; chIdx++) {
        chartSeries.push({
          name: `${resultChannels[chIdx].name} (rep ${r + 1})`,
          type: "line",
          clip: true,
          sampling: "lttb",
          encode: { x: 0, y: chIdx + 1 },
          data: repData,
          showSymbol: false,
          lineStyle: { width: 1, opacity: 0.5 },
        });
      }
    }
  }

  return chartSeries;
}
