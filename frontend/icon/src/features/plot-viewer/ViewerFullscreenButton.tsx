import { useEffect, useState } from "react";
import { Button, Snackbar } from "@mui/material";
import Fullscreen from "@mui/icons-material/Fullscreen";
import FullscreenExit from "@mui/icons-material/FullscreenExit";

export function ViewerFullscreenButton() {
  const [fullscreen, setFullscreen] = useState(Boolean(document.fullscreenElement));
  const [error, setError] = useState(false);
  useEffect(() => {
    const update = () => setFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", update);
    return () => document.removeEventListener("fullscreenchange", update);
  }, []);

  const toggle = async () => {
    setError(false);
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen({ navigationUI: "hide" });
    } catch {
      setError(true);
    }
  };

  return (
    <>
      <Button
        size="small"
        variant="outlined"
        onClick={toggle}
        startIcon={fullscreen ? <FullscreenExit /> : <Fullscreen />}
        title={
          fullscreen
            ? "Exit full screen (Esc)"
            : "Hide the browser frame; Esc returns to the window"
        }
      >
        {fullscreen ? "Exit full screen" : "Full screen"}
      </Button>
      <Snackbar
        open={error}
        autoHideDuration={6000}
        onClose={() => setError(false)}
        message="Full screen is unavailable here. Use your browser's full-screen command (usually F11), or open this plot in a popup."
      />
    </>
  );
}
