import OpenInNew from "@mui/icons-material/OpenInNew";
import { IconButton, Tooltip } from "@mui/material";
import { PlotKind, plotViewerUrl } from "./plotSelection";
import { tryOpenPlotWindow } from "./plotWindow";

export function OpenPlotButton({
  jobId,
  deviceId,
  kind,
  index,
  name,
}: {
  jobId: string;
  deviceId: string;
  kind: PlotKind;
  index: number;
  name: string;
}) {
  return (
    <Tooltip title={`Open ${name} in a popup`}>
      <IconButton
        component="a"
        href={plotViewerUrl(jobId, kind, index, deviceId)}
        onClick={(event) => {
          // Keep Ctrl/Cmd/Shift-click and middle-click as ordinary browser links.
          if (
            event.button !== 0 ||
            event.ctrlKey ||
            event.metaKey ||
            event.shiftKey ||
            event.altKey
          )
            return;
          if (tryOpenPlotWindow(event.currentTarget.href)) event.preventDefault();
        }}
        target="_blank"
        rel="noopener noreferrer"
        size="small"
        aria-label={`Open ${name} in a popup`}
      >
        <OpenInNew fontSize="small" />
      </IconButton>
    </Tooltip>
  );
}
