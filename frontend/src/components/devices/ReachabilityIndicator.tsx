import { Box } from "@mui/material";

export const ReachabilityIndicator = ({
  enabled,
  reachable,
}: {
  enabled: boolean;
  reachable: boolean;
}) => (
  <Box
    component="span"
    sx={{
      display: "inline-block",
      width: 10,
      height: 10,
      borderRadius: "50%",
      bgcolor: enabled ? (reachable ? "green" : "red") : "grey",
      mr: 1,
    }}
  />
);
