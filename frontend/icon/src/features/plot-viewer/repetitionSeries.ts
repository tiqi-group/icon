import type { LineSeriesOption } from "echarts";
import type { ExperimentData } from "../../types/ExperimentData";
import type { ScanParameter } from "../../types/ScanParameter";

/** Overlay original repetitions without shifting missing or truncated samples. */
export function repetitionSeries(
  data: ExperimentData,
  parameter: ScanParameter,
  windowSize: number,
): LineSeriesOption[] {
  const period = parameter.scan_values.length;
  if (!period || parameter.realtime) return [];
  const scan =
    data.scan_parameters[parameter.name] ??
    Object.entries(data.scan_parameters).find(([name]) => name !== "timestamp")?.[1] ??
    {};
  const indices = Object.keys(scan)
    .filter((index) => typeof scan[index] === "number" && Number.isFinite(scan[index]))
    .map(Number)
    .sort((a, b) => a - b);
  const positions = [...new Set(indices.map((index) => index % period))]
    .sort((a, b) => a - b)
    .slice(-windowSize);
  const repetitions = [...new Set(indices.map((index) => Math.floor(index / period)))];
  return Object.entries(data.device_data[0]?.readouts.result_channels ?? {}).flatMap(
    ([name, values]) =>
      repetitions.map((rep) => ({
        name: `${name} (rep ${rep + 1})`,
        type: "line" as const,
        clip: true,
        sampling: "lttb" as const,
        data: positions
          .map((position) => {
            const index = rep * period + position;
            return [
              scan[index] ?? parameter.scan_values[position],
              values[index] ?? Number.NaN,
            ];
          })
          .sort((a, b) => Number(a[0]) - Number(b[0])) as number[][],
        showSymbol: true,
        symbolSize: 4,
        connectNulls: false,
        lineStyle: { width: 1, opacity: 0.5 },
      })),
  );
}
