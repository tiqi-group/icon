import { Tooltip } from "@mui/material";
import { HardwareError } from "../../types/HardwareStatus";

export const ReachabilityIndicator = ({
  enabled,
  status,
}: {
  enabled: boolean;
  status: boolean | HardwareError;
}) => {
  const errorMsg = typeof status == "boolean" ? null : status?.msg;
  const statusStr =
    errorMsg !== null
      ? errorMsg
      : status === true
        ? !enabled
          ? "Disabled (reachable)"
          : "Reachable"
        : !enabled
          ? "Disabled (unreachable)"
          : "Unreachable";

  const reachableColor =
    errorMsg !== null ? undefined : status === true ? "green" : "red";
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
