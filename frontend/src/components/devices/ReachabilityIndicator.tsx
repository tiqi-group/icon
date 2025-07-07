import { Box, Tooltip } from "@mui/material";

export const ReachabilityIndicator = ({
  enabled,
  reachable,
}: {
  enabled: boolean;
  reachable: boolean;
}) => {
  const status = !enabled ? "Disabled" : reachable ? "Reachable" : "Unreachable";

  return (
    <Tooltip title={status}>
      <Box
        component="span"
        sx={{
          display: "flex",
          alignItems: "center",
          width: 15,
          height: 15,
          borderRadius: "50%",
          bgcolor: enabled ? (reachable ? "green" : "red") : "grey",
          mr: 1,
        }}
      />
    </Tooltip>
  );
};
