import { useEffect, useReducer } from "react";
import { ScanParameterInfo } from "../types/ScanParameterInfo";
import { ScanParameterValueGenerator } from "../types/ScanParameterValueGenerator";

export type ScanInfoNavHistory = Record<
  string, // Namespace ID
  {
    displayGroup: string; // Last selected display group for this namespace
    paramByDisplayGroup: Record<
      string, // Display group name
      {
        paramId: string; // Last selected parameter ID for this display group
        generatorByParamId: Record<string, ScanParameterValueGenerator>; // Mapping from parameter ID to last used generator
      }
    >;
  }
>;

class ScanInfoNavHistoryManager {
  constructor(readonly navHistory: ScanInfoNavHistory) {}

  private resolveByNamespace(namespace: string): ScanParameterInfo {
    return this.resolveByDisplayGroup(
      namespace,
      this.navHistory[namespace]?.displayGroup ?? "",
    );
  }

  private resolveByDisplayGroup(
    namespace: string,
    displayGroup: string,
  ): ScanParameterInfo {
    return this.resolveByParamId(
      namespace,
      displayGroup,
      this.navHistory[namespace]?.paramByDisplayGroup[displayGroup]?.paramId ?? "",
    );
  }

  private resolveByParamId(
    namespace: string,
    displayGroup: string,
    paramId: string,
  ): ScanParameterInfo {
    return {
      namespace,
      deviceNameOrDisplayGroup: displayGroup,
      id: paramId,
      generation:
        this.navHistory[namespace]?.paramByDisplayGroup[displayGroup]
          ?.generatorByParamId[paramId] ?? defaultValueGenerator,
    };
  }

  resolveMissingInfo(
    currentParamInfo: ScanParameterInfo,
    paramUpdate: Partial<ScanParameterInfo>,
  ): ScanParameterInfo {
    const updatedParamInfo = { ...currentParamInfo, ...paramUpdate };

    // Update contains generation - nothing to resolve
    if (paramUpdate.generation) {
      return updatedParamInfo;
    }

    // Update contains parameter id. Resolve last generation
    if (paramUpdate.id) {
      return this.resolveByParamId(
        updatedParamInfo.namespace,
        updatedParamInfo.deviceNameOrDisplayGroup,
        paramUpdate.id,
      );
    }

    // Update contains deviceNameOrDisplayGroup. Resolve last id and value generator
    if (paramUpdate.deviceNameOrDisplayGroup) {
      return this.resolveByDisplayGroup(
        updatedParamInfo.namespace,
        paramUpdate.deviceNameOrDisplayGroup,
      );
    }

    // Update contains Namespace. Resolve last deviceNameOrDisplayGroup, id and value generator
    if (paramUpdate.namespace) {
      return this.resolveByNamespace(paramUpdate.namespace);
    }

    return updatedParamInfo;
  }

  update(paramInfo: ScanParameterInfo): ScanInfoNavHistoryManager {
    const {
      namespace,
      deviceNameOrDisplayGroup: displayGroup,
      id,
      generation,
    } = paramInfo;
    const prevNs = this.navHistory[namespace] ?? {
      displayGroup: "",
      paramByDisplayGroup: {},
    };
    const prevDg = prevNs.paramByDisplayGroup[displayGroup] ?? {
      paramId: "",
      generatorByParamId: {},
    };
    const newDg = {
      paramId: id,
      generatorByParamId: { ...prevDg.generatorByParamId, [id]: generation },
    };
    const updatedEntry = {
      [namespace]: {
        displayGroup,
        paramByDisplayGroup: {
          ...prevNs.paramByDisplayGroup,
          [displayGroup]: newDg,
        },
      },
    };

    return new ScanInfoNavHistoryManager({
      ...this.navHistory,
      ...updatedEntry,
    });
  }
}

export interface ScanInfoState {
  priority: number;
  shots: number;
  repetitions: number;
  parameters: ScanParameterInfo[];
  navHistory: ScanInfoNavHistory;
}

export type ScanInfoAction =
  | { type: "RESET"; payload: ScanInfoState }
  | { type: "SET_PRIORITY" | "SET_SHOTS" | "SET_REPETITIONS"; payload: number }
  | { type: "ADD_PARAMETER" }
  | { type: "REMOVE_PARAMETER"; index: number }
  | { type: "UPDATE_PARAMETER"; index: number; payload: Partial<ScanParameterInfo> };

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
  navHistory: {},
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
      navHistory: restored.navHistory ?? {},
    };
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
      if (action.payload.id === "Real Time") {
        newState = {
          ...state,
          parameters: state.parameters.map((p, i) =>
            i === action.index ? { ...p, ...action.payload } : p,
          ),
        };
      } else {
        const navHistoryManager = new ScanInfoNavHistoryManager(state.navHistory);
        const updatedParam = navHistoryManager.resolveMissingInfo(
          state.parameters[action.index],
          action.payload,
        );

        newState = {
          ...state,
          parameters: state.parameters.map((p, i) =>
            i === action.index ? updatedParam : p,
          ),
          navHistory: navHistoryManager.update(updatedParam).navHistory,
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
