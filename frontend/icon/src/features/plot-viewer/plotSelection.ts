import type { ExperimentData, ExperimentDeviceData } from "../../types/ExperimentData";
import type { ScanParameter } from "../../types/ScanParameter";

export type PlotKind = "readout" | "histogram";

export function plotViewerUrl(
  jobId: string,
  kind: PlotKind,
  index: number,
  deviceId: string,
) {
  return `/data/${encodeURIComponent(jobId)}/plot/${kind}/${index}?device=${encodeURIComponent(deviceId)}`;
}

export function selectPlot(
  data: ExperimentData,
  deviceId: string | null,
  kind: string | undefined,
  index: string | undefined,
) {
  if (!index || !/^\d+$/.test(index) || (kind !== "readout" && kind !== "histogram"))
    return null;
  const device =
    deviceId === null
      ? data.device_data[0]
      : data.device_data.find((item) => item.device_id === deviceId);
  const windows =
    kind === "readout"
      ? device?.plot_windows.result_channels
      : device?.plot_windows.shot_channels;
  const plot = windows?.find((item) => item.index === Number(index));
  return device && plot ? { device, plot } : null;
}

/** Align on original point indices, including holes, before existing plot builders zip values. */
export function projectPlotData(
  data: ExperimentData,
  device: ExperimentDeviceData,
  channels: string[],
): ExperimentData {
  const selected = new Set(channels);
  const resultChannels = Object.fromEntries(
    Object.entries(device.readouts.result_channels).filter(([name]) =>
      selected.has(name),
    ),
  );
  const scanMaps = Object.values(data.scan_parameters);
  const indices = [
    ...new Set(Object.values(resultChannels).flatMap((values) => Object.keys(values))),
  ]
    .filter((index) => scanMaps.every((values) => Object.hasOwn(values, index)))
    .sort((a, b) => Number(a) - Number(b));
  return {
    ...data,
    scan_parameters: Object.fromEntries(
      Object.entries(data.scan_parameters).map(([name, values]) => [
        name,
        Object.fromEntries(indices.map((index) => [index, values[index]])),
      ]),
    ),
    device_data: [
      {
        ...device,
        readouts: {
          result_channels: Object.fromEntries(
            Object.entries(resultChannels).map(([name, values]) => [
              name,
              Object.fromEntries(
                indices.map((index) => [index, values[index] ?? Number.NaN]),
              ),
            ]),
          ),
          shot_channels: Object.fromEntries(
            Object.entries(device.readouts.shot_channels).filter(([name]) =>
              selected.has(name),
            ),
          ),
          vector_channels: {},
        },
        fits: Object.fromEntries(
          Object.entries(device.fits ?? {}).filter(([name]) => selected.has(name)),
        ),
      },
    ],
  };
}

/** A retained finite subset must use observed X values, not restart at planned scan point zero. */
export function observedScanParameters(
  data: ExperimentData,
  parameters: ScanParameter[],
): ScanParameter[] {
  if (parameters.length !== 1 || parameters[0].realtime) return parameters;
  const observed = Object.entries(data.scan_parameters).find(
    ([name]) => name !== "timestamp",
  );
  const values = Object.values(observed?.[1] ?? {});
  return values.every(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  )
    ? [{ ...parameters[0], scan_values: values }]
    : parameters;
}

export function hasNumericScanAxis(data: ExperimentData): boolean {
  const axis = Object.entries(data.scan_parameters).find(
    ([name]) => name !== "timestamp",
  );
  return (
    !!axis &&
    Object.values(axis[1]).length > 0 &&
    Object.values(axis[1]).every(
      (value) => typeof value === "number" && Number.isFinite(value),
    )
  );
}

export function hasFittablePoints(data: ExperimentData): boolean {
  if (!hasNumericScanAxis(data)) return false;
  return Object.values(data.device_data[0]?.readouts.result_channels ?? {}).some(
    (values) => Object.values(values).filter(Number.isFinite).length >= 3,
  );
}

/** Preserve JobView's averaging by planned scan position, even for a retained tail. */
export function averageRepeatedPlot(
  data: ExperimentData,
  parameters: ScanParameter[],
  repetitions: number,
): ExperimentData {
  if (
    repetitions <= 1 ||
    parameters.length !== 1 ||
    parameters[0].realtime ||
    !hasNumericScanAxis(data)
  )
    return data;
  const period = parameters[0].scan_values.length;
  if (!period) return data;
  const axis = Object.entries(data.scan_parameters).find(
    ([name]) => name !== "timestamp",
  )!;
  const groups = new Map<number, string[]>();
  for (const index of Object.keys(axis[1])) {
    const position = Number(index) % period;
    groups.set(position, [...(groups.get(position) ?? []), index]);
  }
  const entries = [...groups.entries()].sort(([a], [b]) => a - b);
  return {
    ...data,
    scan_parameters: Object.fromEntries(
      Object.entries(data.scan_parameters).map(([name, values]) => [
        name,
        Object.fromEntries(
          entries.map(([position, indices]) => [position, values[indices[0]]]),
        ),
      ]),
    ),
    device_data: data.device_data.map((device) => ({
      ...device,
      readouts: {
        ...device.readouts,
        result_channels: Object.fromEntries(
          Object.entries(device.readouts.result_channels).map(([name, values]) => [
            name,
            Object.fromEntries(
              entries.map(([position, indices]) => {
                const finite = indices
                  .map((index) => values[index])
                  .filter(Number.isFinite);
                return [
                  position,
                  finite.length
                    ? finite.reduce((sum, value) => sum + value, 0) / finite.length
                    : Number.NaN,
                ];
              }),
            ),
          ]),
        ),
      },
    })),
  };
}
