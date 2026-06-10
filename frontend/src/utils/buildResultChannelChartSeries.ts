import { EChartsOption } from "echarts";

interface Channel {
  name: string;
  data: number[];
}

const ECHARTS_PALETTE = [
  "#5470c6",
  "#91cc75",
  "#fac858",
  "#ee6666",
  "#73c0de",
  "#3ba272",
  "#fc8452",
  "#9a60b4",
  "#ea7ccc",
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function renderErrorBar(_params: unknown, api: any) {
  const x = api.coord([api.value(0), api.value(1)])[0];
  const yHigh = api.coord([api.value(0), api.value(1)])[1];
  const yLow = api.coord([api.value(0), api.value(2)])[1];
  const halfCap = 5;
  const color = api.visual("color");
  const style = { stroke: color, lineWidth: 1.5 };
  return {
    type: "group",
    children: [
      { type: "line", shape: { x1: x, y1: yHigh, x2: x, y2: yLow }, style },
      {
        type: "line",
        shape: { x1: x - halfCap, y1: yHigh, x2: x + halfCap, y2: yHigh },
        style,
      },
      {
        type: "line",
        shape: { x1: x - halfCap, y1: yLow, x2: x + halfCap, y2: yLow },
        style,
      },
    ],
  };
}

/**
 * Build chart series for result channels with optional repetition traces and shot-noise
 * error bars.
 *
 * - Computes a merged dataset by averaging all repetitions for each channel.
 * - Always creates one "merged" series per channel.
 * - Optionally creates one series per channel per repetition (if `showRepetitions` is
 *   true). These repetition series are appended after the merged series and drawn in
 *   lower opacity.
 * - Optionally overlays shot-noise error bars when `showShotNoise` is true and
 *   `shotChannels` is provided. σ = √(p·(1−p)/N) pooled across all repetitions.
 *
 * @param xAxisData - Array of x-values (scan points).
 * @param resultChannels - Array of channel objects { name, data }. Each channel's
 *   `data` is a flat array of values across all repetitions.
 * @param repetitions - Number of experiment repetitions (used to slice channel data).
 * @param showRepetitions - If true, adds individual traces for each repetition.
 * @param shotChannels - Raw per-shot data keyed by channel name then data-point index.
 * @param showShotNoise - If true and shotChannels provided, adds error-bar custom series.
 * @returns EChartsOption["series"] - Series configuration for ECharts.
 */
export function buildResultChannelChartSeries(
  xAxisData: number[],
  resultChannels: Channel[],
  repetitions: number,
  showRepetitions: boolean,
  shotChannels?: Record<string, Record<string, number[]>>,
  showShotNoise?: boolean,
): EChartsOption["series"] {
  const xLen = xAxisData.length;
  const getVal = (ch: Channel, rep: number, i: number): number =>
    Number.isFinite(ch.data[rep * xLen + i]) ? ch.data[rep * xLen + i] : Number.NaN;

  // merged data — sorted by x so lines connect points in scan-parameter order
  const fullDataSet: number[][] = xAxisData
    .map((x, i) => {
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
    })
    .sort((a, b) => a[0] - b[0]);

  // merged series
  const chartSeries: EChartsOption["series"] = resultChannels.map((ch, chIdx) => ({
    name: ch.name,
    type: "line",
    clip: true,
    sampling: "lttb",
    encode: { x: 0, y: chIdx + 1 },
    data: fullDataSet,
    showSymbol: true,
    lineStyle: { width: 2 },
  }));

  if (showRepetitions && repetitions > 1) {
    for (let r = 0; r < repetitions; r++) {
      const repData: number[][] = xAxisData
        .map((x, i) => {
          const ys = resultChannels.map((ch) => {
            const v = getVal(ch, r, i);
            return Number.isFinite(v) ? v : Number.NaN;
          });
          return [x, ...ys];
        })
        .sort((a, b) => a[0] - b[0]);

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

  if (showShotNoise && shotChannels) {
    for (let chIdx = 0; chIdx < resultChannels.length; chIdx++) {
      const ch = resultChannels[chIdx];
      const chShots = shotChannels[ch.name];
      if (!chShots) continue;

      const errorData = xAxisData
        .map((x, i) => {
          let totalN = 0;
          let totalShots = 0;
          for (let r = 0; r < repetitions; r++) {
            const key = (r * xLen + i).toString();
            const shots = chShots[key] ?? [];
            for (const s of shots) {
              if (Number.isFinite(s)) {
                totalN++;
                totalShots += s;
              }
            }
          }
          if (totalN === 0) return [x, Number.NaN, Number.NaN];
          const p = totalShots / totalN;
          const sigma = Math.sqrt((p * (1 - p)) / totalN);
          return [x, p + sigma, p - sigma];
        })
        .sort((a, b) => a[0] - b[0]);

      chartSeries.push({
        name: `${ch.name} ±σ`,
        type: "custom",
        renderItem: renderErrorBar,
        data: errorData,
        itemStyle: { color: ECHARTS_PALETTE[chIdx % ECHARTS_PALETTE.length] },
        z: 3,
        silent: true,
        legendHoverLink: false,
        // hide from legend
        emphasis: { disabled: true },
      } as EChartsOption["series"] extends (infer S)[] ? S : never);
    }
  }

  return chartSeries;
}
