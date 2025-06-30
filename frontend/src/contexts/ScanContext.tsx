import React, { useReducer, createContext, useContext, useState } from "react";
import { Menu, MenuItem } from "@mui/material";
import { ScanParameterInfo } from "../types/ScanParameterInfo";

interface ScanInfoState {
  priority: number;
  shots: number;
  repetitions: number;
  parameters: ScanParameterInfo[];
}

export type Action =
  | { type: "SET_PRIORITY" | "SET_SHOTS" | "SET_REPETITIONS"; payload: number }
  | { type: "ADD_PARAMETER" }
  | { type: "REMOVE_PARAMETER"; index: number }
  | { type: "UPDATE_PARAMETER"; index: number; payload: Partial<ScanParameterInfo> };

const reducer = (state: ScanInfoState, action: Action): ScanInfoState => {
  if (action.type === "ADD_PARAMETER") {
    return {
      ...state,
      parameters: [
        ...state.parameters,
        {
          id: "",
          values: [],
          generation: { start: 0, stop: 0, points: 2, scatter: false },
        },
      ],
    };
  }
  if (action.type === "REMOVE_PARAMETER") {
    return {
      ...state,
      parameters: state.parameters.filter((_, i) => i !== action.index),
    };
  }
  if (action.type === "UPDATE_PARAMETER") {
    return {
      ...state,
      parameters: state.parameters.map((param, i) =>
        i === action.index ? { ...param, ...action.payload } : param,
      ),
    };
  }
  return { ...state, [action.type.toLowerCase().replace("set_", "")]: action.payload };
};

const ScanContext = createContext<{
  state: ScanInfoState;
  dispatch: React.Dispatch<Action>;
  menuAnchor: { mouseX: number | null; mouseY: number | null };
  handleRightClick: (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    deviceName?: string,
  ) => void;
  handleCloseMenu: () => void;
}>({
  state: { priority: 20, shots: 50, repetitions: 1, parameters: [] },
  dispatch: () => {},
  menuAnchor: { mouseX: null, mouseY: null },
  handleRightClick: () => {},
  handleCloseMenu: () => {},
});

export const ScanProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(reducer, {
    priority: 20,
    shots: 50,
    repetitions: 1,
    parameters: [
      {
        id: "",
        values: [],
        generation: { start: 0, stop: 0, points: 2, scatter: false },
      },
    ],
  });

  const [menuAnchor, setMenuAnchor] = useState<{
    mouseX: number | null;
    mouseY: number | null;
  }>({
    mouseX: null,
    mouseY: null,
  });

  const [selectedParam, setSelectedParam] = useState<{
    id: string;
    device_name?: string;
  } | null>(null);

  const handleRightClick = (
    event: React.MouseEvent<HTMLDivElement | HTMLButtonElement>,
    paramId: string,
    deviceName?: string,
  ) => {
    console.log(`Right-clicked on: ${paramId}`);
    event.preventDefault();
    setSelectedParam({ id: paramId, device_name: deviceName });
    setMenuAnchor({ mouseX: event.clientX, mouseY: event.clientY });
  };

  const handleCloseMenu = () => {
    setMenuAnchor({ mouseX: null, mouseY: null });
    setSelectedParam(null);
  };

  return (
    <ScanContext.Provider
      value={{ state, dispatch, menuAnchor, handleRightClick, handleCloseMenu }}
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
        {state.parameters.length > 0 ? (
          state.parameters.map((_, index) => (
            <MenuItem
              key={index}
              onClick={() => {
                dispatch({
                  type: "UPDATE_PARAMETER",
                  index,
                  payload: {
                    id: selectedParam!.id,
                    device_name: selectedParam?.device_name,
                  },
                });
                handleCloseMenu();
                console.log(
                  `Set parameter ${index + 1} to ${selectedParam!.id} ${selectedParam?.device_name}`,
                );
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

export const useScanContext = () => useContext(ScanContext);
