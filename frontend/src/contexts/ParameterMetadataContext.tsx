import { createContext } from "react";
import { ParameterMetadata } from "../types/ExperimentMetadata";

export const ParameterMetadataContext = createContext<
  Record<string, ParameterMetadata>
>({});
