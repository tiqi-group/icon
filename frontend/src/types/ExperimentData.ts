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

export interface ExperimentData {
  shot_channels: Record<string, Record<string, number[]>>;
  result_channels: Record<string, Record<string, number>>;
  vector_channels: Record<string, Record<string, number[]>>;
  scan_parameters: Record<string, Record<string, number | boolean | string>>;
  json_sequences: [number, string][];
}
