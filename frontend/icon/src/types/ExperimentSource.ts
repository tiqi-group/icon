import { Job } from "./Job";

export interface ExperimentSource {
  id: number;
  experiment_id: string;
  jobs?: Job[];
}
