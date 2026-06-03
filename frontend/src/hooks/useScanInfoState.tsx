import { useEffect, useReducer } from "react";
import { ScanParameterInfo } from "../types/ScanParameterInfo";
import { ScanParameterValueGenerator } from "../types/ScanParameterValueGenerator";

export interface ScanInfoState {
  priority: number;
  shots: number;
  repetitions: number;
  parameters: ScanParameterInfo[];
  valueGenerators: Record<string, ScanParameterValueGenerator>;
}

export type ScanInfoAction =
  | { type: "RESET"; payload: ScanInfoState }
  | { type: "SET_PRIORITY" | "SET_SHOTS" | "SET_REPETITIONS"; payload: number }
  | { type: "ADD_PARAMETER" }
  | { type: "REMOVE_PARAMETER"; index: number }
  | {
      type: "UPDATE_PARAMETER";
      index: number;
      parameter_id: string;
      payload: Partial<ScanParameterInfo>;
    };

const defaultValueGenerator: ScanParameterValueGenerator = {
  start: 0,
  stop: 1,
  points: 2,
  pattern: "linear",
};

const defaultParameter: ScanParameterInfo = {
  id: "",
  generation: defaultValueGenerator,
  namespace: "",
  deviceNameOrDisplayGroup: "",
};
export const defaultScanInfoState: ScanInfoState = {
  priority: 20,
  shots: 50,
  repetitions: 1,
  parameters: [defaultParameter],
  valueGenerators: { "": defaultValueGenerator },
};

const STORAGE_KEY_PREFIX = "scanInfoState:";

const saveScanInfoStateToLocalStorage = (
  experimentId: string,
  state: ScanInfoState,
) => {
  try {
    localStorage.setItem(`${STORAGE_KEY_PREFIX}${experimentId}`, JSON.stringify(state));
  } catch (e) {
    console.error("Failed to save scan info state", e);
  }
};

const getScanInfoStateFromLocalStorage = (experimentId: string): ScanInfoState => {
  const data = localStorage.getItem(`${STORAGE_KEY_PREFIX}${experimentId}`);
  if (data) {
    const restoredScanInfoState = JSON.parse(data) as ScanInfoState;
    // Backwards compatibility: if valueGenerators is not present, populate with default
    return !restoredScanInfoState.valueGenerators
      ? {
          ...restoredScanInfoState,
          valueGenerators: { "": defaultValueGenerator },
        }
      : restoredScanInfoState;
  } else {
    saveScanInfoStateToLocalStorage(experimentId, defaultScanInfoState);
    return defaultScanInfoState;
  }
};

const reducer =
  (experimentId: string) => (state: ScanInfoState, action: ScanInfoAction) => {
    let newState: ScanInfoState;

    if (action.type === "RESET") {
      return action.payload;
    } else if (action.type === "ADD_PARAMETER") {
      newState = { ...state, parameters: [...state.parameters, defaultParameter] };
    } else if (action.type === "REMOVE_PARAMETER") {
      newState = {
        ...state,
        parameters: state.parameters.filter((_, i) => i !== action.index),
      };
    } else if (action.type === "UPDATE_PARAMETER") {
      // Update valueGenerators if generation info was changed
      const valueGenerators =
        action.payload.generation != null
          ? {
              ...state.valueGenerators,
              [action.parameter_id]: action.payload.generation,
            }
          : state.valueGenerators;

      // Retrieve generation description from valueGenerators if generation did not change
      const payload =
        action.payload.generation == null
          ? {
              ...action.payload,
              generation:
                state.valueGenerators[action.parameter_id] ?? defaultValueGenerator,
            }
          : action.payload;

      newState = {
        ...state,
        parameters: state.parameters.map((param, i) =>
          i === action.index ? { ...param, ...payload } : param,
        ),
        valueGenerators: valueGenerators,
      };
    } else {
      newState = {
        ...state,
        [action.type.toLowerCase().replace("set_", "")]: action.payload,
      };
    }

    saveScanInfoStateToLocalStorage(experimentId, newState);
    return newState;
  };

export const useScanInfoState = (experimentId: string) => {
  const [scanInfoState, dispatchScanInfoStateUpdate] = useReducer(
    reducer(experimentId),
    getScanInfoStateFromLocalStorage(experimentId),
  );

  useEffect(() => {
    dispatchScanInfoStateUpdate({
      type: "RESET",
      payload: getScanInfoStateFromLocalStorage(experimentId),
    });
  }, [experimentId]);

  return { scanInfoState, dispatchScanInfoStateUpdate };
};
