interface Readouts {
  result_channels: Record<string, number>;
  vector_channels: Record<string, number[]>;
  shot_channels: Record<string, number[]>;
}

export interface ExperimentDeviceDataPoint {
  device_id: string;
  readouts: Readouts;
  hardware_instructions: string;
}

export interface ExperimentDataPoint {
  index: number;
  scan_params: Record<string, number | boolean | string>;
  timestamp: string;
  device_data: ExperimentDeviceDataPoint[];
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

export interface ReadoutSequences {
  result_channels: Record<string, Record<string, number>>;
  vector_channels: Record<string, Record<string, number[]>>;
  shot_channels: Record<string, Record<string, number[]>>;
}

export interface ExperimentDeviceData {
  device_id: string;
  readouts: ReadoutSequences;
  plot_windows: PlotWindows;
  hardware_instructions: [number, string][];
  fits: Record<string, FitResult>;
}

export interface ExperimentData {
  device_data: ExperimentDeviceData[];
  scan_parameters: Record<string, Record<string, number | boolean | string>>;
  parameters: Record<string, ParameterValue>;
  total_data_points: number;
}
