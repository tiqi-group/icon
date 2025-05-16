import { createContext } from "react";
import { ParameterMetadata } from "../types/ExperimentMetadata";

export const ParameterDisplayGroupsContext = createContext<
  [Record<string, Record<string, ParameterMetadata>>, Record<string, string[]>]
>([{}, {}]);
