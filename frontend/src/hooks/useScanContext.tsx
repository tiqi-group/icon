import { useContext } from "react";
import { ScanContext } from "../contexts/ScanContext";

export const useScanContext = () => useContext(ScanContext);
