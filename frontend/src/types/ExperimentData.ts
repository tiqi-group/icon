interface ResultDict {
  result_channels: Record<string, number>;
  vector_channels: Record<string, number[]>;
  shot_channels: Record<string, number[]>;
}

export type ExperimentDataPoint = ResultDict & {
  index: number;
  scan_params: Record<string, number | boolean | string>;
  timestamp: string;
};

export interface ExperimentData {
  shot_channels: Record<string, Record<number, number[]>>;
  result_channels: Record<string, Record<number, number>>;
  vector_channels: Record<string, Record<number, number[]>>;
  scan_parameters: Record<string, Record<number, number | boolean | string>>;
}
