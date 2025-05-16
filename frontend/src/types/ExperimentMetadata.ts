export interface ParameterMetadata {
  display_name: string;
  unit: string;
  default_value: number | boolean;
  min_value: number | null;
  max_value: number | null;
  read_only?: boolean;
}

interface ExperimentMetadata {
  class_name: string;
  constructor_kwargs: Record<string, string>;
  parameters: Record<string, Record<string, ParameterMetadata>>;
}

export type ExperimentDict = Record<string, ExperimentMetadata>;
