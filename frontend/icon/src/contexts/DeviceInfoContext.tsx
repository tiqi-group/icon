import { createContext } from "react";
import { DeviceInfo } from "../types/DeviceInfo";

export interface DeviceUpdate {
  device_name: string;
  updated_properties: Record<string, string>;
}

export type Devices = Record<string, DeviceInfo>;

export type Action =
  | { type: "SET"; payload: Devices }
  | { type: "ADD"; payload: DeviceInfo }
  | { type: "UPDATE"; payload: DeviceUpdate };

// Reducer Function
export const deviceInfoReducer = (state: Devices, action: Action): Devices => {
  switch (action.type) {
    case "SET":
      return { ...state, ...action.payload };
    case "ADD":
      return { ...state, [action.payload.name]: action.payload };
    case "UPDATE": {
      const device = state[action.payload.device_name];
      // job not found, no update
      if (!device) return state;

      return {
        ...state,
        [action.payload.device_name]: {
          ...device,
          ...action.payload.updated_properties,
        },
      };
    }
    default:
      return state;
  }
};

export const DeviceInfoContext = createContext<Devices>({});
