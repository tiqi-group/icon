import { createContext } from "react";
import { ExperimentDict } from "../types/ExperimentMetadata";

export const ExperimentsContext = createContext<ExperimentDict>({});
