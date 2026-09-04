interface Readouts {
  result_channels: Record<string, number>;
  vector_channels: Record<string, number[]>;
  shot_channels: Record<string, number[]>;
}

interface ReadoutSequences {
  result_channels: Record<string, Record<string, number>>;
  vector_channels: Record<string, Record<string, number[]>>;
  shot_channels: Record<string, Record<string, number[]>>;
}

export interface ExperimentDataPoint {
  index: number;
  scan_params: Record<string, number | boolean | string>;
  timestamp: string;
  readouts: Readouts;
  hardware_instructions: string;
}

interface PlotWindowMetadata {
  name: string;
  index: number;
  type: "readout" | "histogram" | "vector";
  channel_names: string[];
}

export interface PlotWindows {
  result_channels: PlotWindowMetadata[];
  shot_channels: PlotWindowMetadata[];
  vector_channels: PlotWindowMetadata[];
}

export interface ParameterValue {
  timestamp: string;
  value: string | number | boolean;
}

export interface FitResult {
  result_channel: string;
  func_type: string;
  x_range: [number, number] | null;
  init: Record<string, number>;
  result: Record<string, number>;
  goodness: Record<string, number>;
  success: boolean;
  message: string;
  fit_curve?: { x: number[]; y: number[] };
}

export interface ExperimentData {
  plot_windows: PlotWindows;
  readouts: ReadoutSequences;
  scan_parameters: Record<string, Record<string, number | boolean | string>>;
  hardware_instructions: [number, string][];
  parameters: Record<string, ParameterValue>;
  total_data_points: number;
  fits: Record<string, FitResult>;
}
