import { createContext } from "react";
import { ScanInfoAction, ScanInfoState } from "../hooks/useScanInfoState";

interface ScanContextValue {
  scanInfoState: ScanInfoState;
  dispatchScanInfoStateUpdate: React.Dispatch<ScanInfoAction>;
  menuAnchor: { mouseX: number | null; mouseY: number | null };
  handleRightClick: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    deviceNameOrDisplayGroup: string,
    namespace: string,
  ) => void;
  handleCloseMenu: () => void;
  scannedParamKeys: string[];
}

export const ScanContext = createContext<ScanContextValue | undefined>(undefined);
