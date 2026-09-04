import { useEffect, useReducer } from "react";
import { ScanMode } from "../types/enums";
import { ScanParameterInfo } from "../types/ScanParameterInfo";
import { ScanParameterGenerationSpec } from "../types/ScanParameterGenerationSpec";
import {
  SerializedScanInfoSelectionHistory,
  ScanInfoSelectionHistory,
  emptyScanInfoHistory,
} from "../utils/ScanInfoSelectionHistory";

export interface ScanInfoState {
  priority: number;
  shots: number;
  repetitions: number;
  scanMode: ScanMode;
  parameters: ScanParameterInfo[];
  history: SerializedScanInfoSelectionHistory;
}

export type ScanInfoAction =
  | { type: "RESET"; payload: ScanInfoState }
  | { type: "SET_PRIORITY" | "SET_SHOTS" | "SET_REPETITIONS"; payload: number }
  | { type: "SET_SCAN_MODE"; payload: ScanMode }
  | { type: "ADD_PARAMETER" }
  | { type: "REMOVE_PARAMETER"; index: number }
  | { type: "UPDATE_PARAMETER"; index: number; payload: Partial<ScanParameterInfo> };

const defaultParameterGenerationSpec: ScanParameterGenerationSpec = {
  start: 0,
  stop: 1,
  points: 2,
  pattern: "linear",
};

export const defaultParameter: ScanParameterInfo = {
  id: "",
  generation: defaultParameterGenerationSpec,
  namespace: "",
  deviceNameOrDisplayGroup: "",
};
export const defaultScanInfoState: ScanInfoState = {
  priority: 20,
  shots: 50,
  repetitions: 1,
  scanMode: ScanMode.MESH,
  parameters: [defaultParameter],
  history: emptyScanInfoHistory,
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
    const restored = JSON.parse(data) as ScanInfoState;
    return {
      ...restored,
      history: restored.history ?? emptyScanInfoHistory,
      scanMode: restored.scanMode ?? ScanMode.MESH,
    };
  } else {
    saveScanInfoStateToLocalStorage(experimentId, defaultScanInfoState);
    return defaultScanInfoState;
  }
};

export const reducer =
  (experimentId: string) => (state: ScanInfoState, action: ScanInfoAction) => {
    let newState: ScanInfoState;

    if (action.type === "RESET") {
      return action.payload;
    } else if (action.type === "SET_SCAN_MODE") {
      // Handled explicitly: the generic branch below would derive the key "scan_mode".
      newState = { ...state, scanMode: action.payload };
    } else if (action.type === "ADD_PARAMETER") {
      newState = { ...state, parameters: [...state.parameters, defaultParameter] };
    } else if (action.type === "REMOVE_PARAMETER") {
      newState = {
        ...state,
        parameters: state.parameters.filter((_, i) => i !== action.index),
      };
    } else if (action.type === "UPDATE_PARAMETER") {
      if (action.payload.id === "Real Time" || action.payload.n_scan_points != null) {
        newState = {
          ...state,
          parameters: state.parameters.map((p, i) =>
            i === action.index ? { ...p, ...action.payload } : p,
          ),
        };
      } else {
        const { updatedParam, updatedScanInfoHistory } = new ScanInfoSelectionHistory(
          () => defaultParameterGenerationSpec,
          state.history,
        ).handleParamUpdate(state.parameters[action.index], action.payload);
        newState = {
          ...state,
          parameters: state.parameters.map((p, i) =>
            i === action.index ? updatedParam : p,
          ),
          history: updatedScanInfoHistory,
        };
      }
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
