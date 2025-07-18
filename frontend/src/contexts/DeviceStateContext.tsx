// DeviceStateContext.tsx
import { createContext } from "react";
import { SerializedDict, SerializedObject } from "../types/SerializedObject";
import { setNestedValueByPath } from "../utils/stateUtils";

export interface DeviceState {
  value: {
    devices: {
      value: {
        device_proxies: SerializedDict;
      };
    };
  };
}

export type StateAction =
  | { type: "SET"; data: DeviceState }
  | {
      type: "UPDATE";
      fullAccessPath: string;
      newValue: SerializedObject;
    };

export const deviceStateReducer = (
  state: DeviceState | null,
  action: StateAction,
): DeviceState | null => {
  switch (action.type) {
    case "SET":
      return action.data;
    case "UPDATE": {
      if (state === null) {
        return null;
      }
      return {
        ...state,
        value: setNestedValueByPath(
          state.value as unknown as Record<string, SerializedObject>,
          action.fullAccessPath,
          action.newValue,
        ) as unknown as DeviceState["value"],
      };
    }
    default:
      throw new Error();
  }
};

export const DeviceStateContext = createContext<DeviceState | null>(null);
