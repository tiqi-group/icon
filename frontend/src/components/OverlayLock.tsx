import { Button } from "@mui/material";
import { socket } from "../socket";

interface OverlayLockProps {
  isLockedByOther: boolean;
}

export function OverlayLock({ isLockedByOther }: OverlayLockProps) {
  if (!isLockedByOther) return null;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: "rgba(128,128,128,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        style={{
          background: "var(--mui-palette-common-background)",
          padding: "1rem 2rem",
          borderRadius: "6px",
          textAlign: "center",
        }}
      >
        <h2
          style={{
            marginBottom: "1rem",
            color: "var(--mui-palette-text-primary)",
            fontSize: "1.5rem",
          }}
        >
          ICON is Locked
        </h2>
        <p
          style={{
            fontSize: "1rem",
            color: "var(--mui-palette-text-secondary)",
            marginBottom: "1.5rem",
          }}
        >
          Another client is currently controlling ICON.
        </p>
        <Button
          variant="contained"
          color="primary"
          onClick={() => socket.emit("take_control")}
        >
          Take Control
        </Button>
      </div>
    </div>
  );
}
