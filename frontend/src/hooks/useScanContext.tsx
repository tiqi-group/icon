import { useContext } from "react";
import { ScanContext } from "../contexts/ScanContext";
import { defaultScanInfoState } from "./useScanInfoState";

export const useScanContext = () => {
  const context = useContext(ScanContext);
  if (!context) {
    return {
      scanInfoState: defaultScanInfoState,
      dispatchScanInfoStateUpdate: () => {},
      menuAnchor: { mouseX: null, mouseY: null },
      handleRightClick: () => {},
      handleCloseMenu: () => {},
      scannedParamKeys: [],
    };
  }
  return context;
};
