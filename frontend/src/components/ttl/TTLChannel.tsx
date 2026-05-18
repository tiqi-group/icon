import { useState, KeyboardEvent } from "react";
import Box from "@mui/material/Box";
import IconButton from "@mui/material/IconButton";
import TextField from "@mui/material/TextField";
import Typography from "@mui/material/Typography";
import Tooltip from "@mui/material/Tooltip";
import FiberManualRecordIcon from "@mui/icons-material/FiberManualRecord";
import MemoryIcon from "@mui/icons-material/Memory";

interface Props {
  channel: number;
  /** Hardware state: 0=OFF, 1=ON, 2=CONTROL */
  state: number;
  /** Remembered manual ON(1)/OFF(0), persisted independently of CONTROL mode */
  localManualState: 0 | 1;
  label: string;
  onSetState: (state: number) => void;
  onSetLocalManual: (manual: 0 | 1) => void;
  onSetLabel: (label: string) => void;
}

export function TTLChannel({
  channel,
  state,
  localManualState,
  label,
  onSetState,
  onSetLocalManual,
  onSetLabel,
}: Props) {
  const [editingLabel, setEditingLabel] = useState(false);
  const [labelDraft, setLabelDraft] = useState(label);

  const inControl = state === 2;

  function handleControlClick() {
    if (inControl) {
      // CONTROL → manual: apply the remembered manual state
      onSetState(localManualState);
    } else {
      // manual → CONTROL
      onSetState(2);
    }
  }

  function handleStateClick() {
    const newManual: 0 | 1 = localManualState === 1 ? 0 : 1;
    onSetLocalManual(newManual);
    if (!inControl) {
      onSetState(newManual);
    }
  }

  function handleLabelCommit() {
    setEditingLabel(false);
    const trimmed = labelDraft.trim() || label;
    setLabelDraft(trimmed);
    if (trimmed !== label) {
      onSetLabel(trimmed);
    }
  }

  function handleLabelKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter") handleLabelCommit();
    if (e.key === "Escape") {
      setLabelDraft(label);
      setEditingLabel(false);
    }
  }

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 0.5,
        px: 1,
        py: 0.5,
        borderRadius: 1,
        border: "1px solid",
        borderColor: "divider",
        bgcolor: "background.paper",
        minWidth: 0,
      }}
    >
      {/* ControlButton: blue = CONTROL (FPGA owns channel), grey = manual */}
      <Tooltip title={inControl ? "FPGA control (click for manual override)" : "Manual override (click for FPGA control)"}>
        <IconButton
          size="small"
          onClick={handleControlClick}
          color={inControl ? "primary" : "default"}
          sx={{ p: 0.25 }}
        >
          <MemoryIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Tooltip>

      {/* StateButton: green = ON, red = OFF; faded when in CONTROL */}
      <Tooltip title={localManualState === 1 ? "ON (click for OFF)" : "OFF (click for ON)"}>
        <IconButton
          size="small"
          onClick={handleStateClick}
          sx={{
            p: 0.25,
            color: localManualState === 1 ? "success.main" : "error.main",
            opacity: inControl ? 0.35 : 1,
          }}
        >
          <FiberManualRecordIcon sx={{ fontSize: 16 }} />
        </IconButton>
      </Tooltip>

      {/* Editable label */}
      {editingLabel ? (
        <TextField
          size="small"
          value={labelDraft}
          onChange={(e) => setLabelDraft(e.target.value)}
          onBlur={handleLabelCommit}
          onKeyDown={handleLabelKeyDown}
          autoFocus
          slotProps={{ input: { style: { fontSize: 12, padding: "2px 6px" } } }}
          sx={{ width: 90 }}
        />
      ) : (
        <Tooltip title="Double-click to rename">
          <Typography
            variant="caption"
            onDoubleClick={() => {
              setLabelDraft(label);
              setEditingLabel(true);
            }}
            sx={{
              cursor: "text",
              userSelect: "none",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              minWidth: 0,
            }}
          >
            {label}
          </Typography>
        </Tooltip>
      )}
    </Box>
  );
}
