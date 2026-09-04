import React, { useState, ReactNode } from "react";
import { Menu, MenuItem } from "@mui/material";
import { useScanInfoState } from "../hooks/useScanInfoState";
import { makeScannedParamKey } from "../utils/scanUtils";
import { ScanContext } from "./ScanContext";

export const ScanProvider = ({
  experimentId,
  children,
}: {
  experimentId: string;
  children: ReactNode;
}) => {
  const { scanInfoState, dispatchScanInfoStateUpdate } = useScanInfoState(experimentId);

  const scannedParamKeys = scanInfoState.parameters.map((param) =>
    makeScannedParamKey(param.id, param.namespace, param.deviceNameOrDisplayGroup),
  );

  const [menuAnchor, setMenuAnchor] = useState<{
    mouseX: number | null;
    mouseY: number | null;
  }>({
    mouseX: null,
    mouseY: null,
  });

  const [selectedParam, setSelectedParam] = useState<{
    id: string;
    namespace: string;
    deviceNameOrDisplayGroup: string;
  } | null>(null);

  const handleRightClick = (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    deviceNameOrDisplayGroup: string,
    namespace: string,
  ) => {
    event.preventDefault();
    setSelectedParam({ id: paramId, namespace, deviceNameOrDisplayGroup });
    setMenuAnchor({ mouseX: event.clientX, mouseY: event.clientY });
  };

  const handleCloseMenu = () => {
    setMenuAnchor({ mouseX: null, mouseY: null });
    setSelectedParam(null);
  };

  return (
    <ScanContext.Provider
      value={{
        scanInfoState,
        dispatchScanInfoStateUpdate,
        menuAnchor,
        handleRightClick,
        handleCloseMenu,
        scannedParamKeys,
        experimentId,
      }}
    >
      {children}

      <Menu
        open={menuAnchor.mouseY !== null}
        onClose={handleCloseMenu}
        anchorReference="anchorPosition"
        anchorPosition={
          menuAnchor.mouseY !== null && menuAnchor.mouseX !== null
            ? { top: menuAnchor.mouseY, left: menuAnchor.mouseX }
            : undefined
        }
      >
        {scanInfoState.parameters.length > 0 ? (
          scanInfoState.parameters.map((_, index) => (
            <MenuItem
              key={index}
              onClick={() => {
                if (selectedParam) {
                  dispatchScanInfoStateUpdate({
                    type: "UPDATE_PARAMETER",
                    index,
                    payload: {
                      id: selectedParam.id,
                      namespace: selectedParam.namespace,
                      deviceNameOrDisplayGroup: selectedParam.deviceNameOrDisplayGroup,
                    },
                  });
                }
                handleCloseMenu();
              }}
            >
              Scan as parameter {index + 1}
            </MenuItem>
          ))
        ) : (
          <MenuItem disabled>No Scan Variables Available</MenuItem>
        )}
      </Menu>
    </ScanContext.Provider>
  );
};
