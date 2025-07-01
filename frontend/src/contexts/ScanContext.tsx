import React, { createContext } from "react";
import { Action, ScanInfoState } from "./ScanProvider";

export const ScanContext = createContext<{
  state: ScanInfoState;
  dispatch: React.Dispatch<Action>;
  menuAnchor: { mouseX: number | null; mouseY: number | null };
  handleRightClick: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    deviceNameOrDisplayGroup: string,
    namespace: string,
  ) => void;
  handleCloseMenu: () => void;
}>({
  state: { priority: 20, shots: 50, repetitions: 1, parameters: [] },
  dispatch: () => {},
  menuAnchor: { mouseX: null, mouseY: null },
  handleRightClick: () => {},
  handleCloseMenu: () => {},
});
