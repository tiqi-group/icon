export interface HeatmapPoint {
  /** [x category, y category, value] */
  value: [string, string, number];
  /** Time at which this data point was acquired, if known. */
  timestamp?: string;
}

interface Axis {
  realtime: boolean;
  scanValues: number[];
}

/**
 * Builds the heatmap data of a 2D scan.
 *
 * Data points are ordered by acquisition index. If one of the axes is a realtime
 * axis, the ordinary parameter is swept once per realtime step, i.e. data point `i`
 * belongs to sweep `floor(i / n)` and ordinary scan point `i % n`, where `n` is the
 * number of ordinary scan values.
 *
 * The realtime axis category of a sweep is the timestamp of the first data point of
 * that sweep, while each point carries its own acquisition timestamp so it can be
 * shown in the tooltip.
 *
 * @param x - The x scan parameter.
 * @param y - The y scan parameter.
 * @param channelData - Result channel values, ordered by acquisition index.
 * @param timestamps - Acquisition timestamps, ordered by acquisition index.
 * @returns The heatmap points and, for a realtime axis, the category of each sweep.
 */
export function build2DHeatmapData(
  x: Axis,
  y: Axis,
  channelData: number[],
  timestamps: string[],
): { data: HeatmapPoint[]; sweepLabels: string[] } {
  const data: HeatmapPoint[] = [];
  const sweepLabels: string[] = [];

  if (x.realtime || y.realtime) {
    const ordinary = x.realtime ? y.scanValues : x.scanValues;
    const n = ordinary.length;
    if (n === 0) return { data, sweepLabels };

    for (let i = 0; i < channelData.length; i++) {
      const sweep = Math.floor(i / n);
      if (i % n === 0) sweepLabels.push(timestamps[i] ?? String(sweep));
      const sweepLabel = sweepLabels[sweep];
      const ordinaryValue = String(ordinary[i % n]);
      data.push({
        value: x.realtime
          ? [sweepLabel, ordinaryValue, channelData[i]]
          : [ordinaryValue, sweepLabel, channelData[i]],
        timestamp: timestamps[i],
      });
    }
    return { data, sweepLabels };
  }

  const ny = y.scanValues.length;
  for (let i = 0; i < x.scanValues.length; i++) {
    for (let j = 0; j < ny; j++) {
      const index = i * ny + j;
      data.push({
        value: [String(x.scanValues[i]), String(y.scanValues[j]), channelData[index]],
        timestamp: timestamps[index],
      });
    }
  }
  return { data, sweepLabels };
}
