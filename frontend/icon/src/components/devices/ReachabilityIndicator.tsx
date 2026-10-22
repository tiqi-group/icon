import { Tooltip } from "@mui/material";

export const ReachabilityIndicator = ({
  enabled,
  status,
  errorMsg,
}: {
  enabled: boolean;
  status: boolean;
  errorMsg?: string | null;
}) => {
  const error = errorMsg !== null && errorMsg !== undefined;
  const statusStr = error
    ? errorMsg
    : status === true
      ? !enabled
        ? "Disabled (reachable)"
        : "Reachable"
      : !enabled
        ? "Disabled (unreachable)"
        : "Unreachable";

  const reachableColor = error ? undefined : status ? "green" : "red";
  const enabledColor = enabled ? reachableColor : "grey";

  return (
    <Tooltip title={statusStr}>
      {reachableColor !== undefined && enabledColor !== undefined ? (
        <span
          style={{
            display: "flex",
            alignItems: "center",
            width: 15,
            height: 15,
            borderRadius: "50%",
            /* Actually not a gradient, but a sharp split:  */
            background: `linear-gradient(to right, ${enabledColor} 75%, ${reachableColor} 75%)`,
            marginRight: 8,
          }}
        />
      ) : (
        <span style={{ display: "flex", alignItems: "center", marginRight: 8 }}>
          ⚠️
        </span>
      )}
    </Tooltip>
  );
};
