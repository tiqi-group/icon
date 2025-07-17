export type ParameterValueType = number | boolean | string;

export interface ParameterMetadata {
  display_name: string;
  unit: string;
  default_value: ParameterValueType;
  min_value: number | null;
  max_value: number | null;
  read_only?: boolean;
  allowed_values?: string[];
}

export interface ExperimentMetadata {
  class_name: string;
  constructor_kwargs: Record<string, string>;
  parameters: Record<string, Record<string, ParameterMetadata>>;
}

export type ExperimentDict = Record<string, ExperimentMetadata>;
