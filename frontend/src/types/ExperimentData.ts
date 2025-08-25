interface ResultDict {
  result_channels: Record<string, number>;
  vector_channels: Record<string, number[]>;
  shot_channels: Record<string, number[]>;
}

export type ExperimentDataPoint = ResultDict & {
  index: number;
  scan_params: Record<string, number | boolean | string>;
  timestamp: string;
  sequence_json: string;
};
interface PlotWindowMetadata {
  name: string;
  index: number;
  type: "readout" | "histogram" | "vector";
  channel_names: string[];
}

interface PlotWindows {
  result_channels: PlotWindowMetadata[];
  shot_channels: PlotWindowMetadata[];
  vector_channels: PlotWindowMetadata[];
}

export interface ExperimentData {
  plot_windows: PlotWindows;
  shot_channels: Record<string, Record<string, number[]>>;
  result_channels: Record<string, Record<string, number>>;
  vector_channels: Record<string, Record<string, number[]>>;
  scan_parameters: Record<string, Record<string, number | boolean | string>>;
  json_sequences: [number, string][];
}
