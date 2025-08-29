import { useContext } from "react";
import { ScanContext } from "../contexts/ScanContext";
import { defaultScanInfoState } from "./useScanInfoState";

const defaultScanContext = {
  scanInfoState: defaultScanInfoState,
  dispatchScanInfoStateUpdate: () => {},
  menuAnchor: { mouseX: null, mouseY: null },
  handleRightClick: () => {},
  handleCloseMenu: () => {},
  scannedParamKeys: [],
};

export const useScanContext = () => {
  const context = useContext(ScanContext);
  if (!context) {
    return defaultScanContext;
  }
  return context;
};
