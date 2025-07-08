import { Tooltip } from "@mui/material";

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
      <span
        style={{
          display: "flex",
          alignItems: "center",
          width: 15,
          height: 15,
          borderRadius: "50%",
          backgroundColor: enabled ? (reachable ? "green" : "red") : "grey",
          marginRight: 8,
        }}
      />
    </Tooltip>
  );
};
