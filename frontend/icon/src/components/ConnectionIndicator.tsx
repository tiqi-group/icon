import { keyframes } from "@emotion/react";
import { Box, Tooltip, Typography } from "@mui/material";
import { useSocketConnected } from "../hooks/useSocketConnected";

const fadeInOut = keyframes`
  0%, 100% { opacity: 0.2; }
  50% { opacity: 1; }
`;

const labelSx = {
  fontSize: "0.7rem",
  fontWeight: 500,
  whiteSpace: "nowrap",
} as const;

/**
 * Topbar indicator for the websocket connection to the backend.
 */
export function ConnectionIndicator() {
  const connected = useSocketConnected();

  const label = connected ? "●" : "Connecting ●";
  const color = connected ? "success.main" : "error.main";

  return (
    <Tooltip
      title={
        connected
          ? "Connected to the ICON backend."
          : "No connection to the ICON backend. Trying to connect..."
      }
    >
      <Box
        role="status"
        sx={{
          position: "relative",
          display: "inline-flex",
          alignItems: "center",
          px: 0.75,
        }}
      >
        <Typography
          aria-hidden
          variant="caption"
          sx={{
            ...labelSx,
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color,
            filter: "blur(3px)",
            pointerEvents: "none",
            ...(connected
              ? {}
              : {
                  animation: `${fadeInOut} 2.4s ease-in-out infinite`,
                  "@media (prefers-reduced-motion: reduce)": {
                    animation: "none",
                    opacity: 0.6,
                  },
                }),
          }}
        >
          {label}
        </Typography>
        <Typography variant="caption" sx={{ ...labelSx, position: "relative", color }}>
          {label}
        </Typography>
      </Box>
    </Tooltip>
  );
}
