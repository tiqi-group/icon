import { useColorScheme } from "@mui/material/styles";
import { useSearchParams } from "react-router";
import { hostname, port } from "../socket";

export function VisualiserPage() {
  const { mode, systemMode } = useColorScheme();
  const [searchParams] = useSearchParams();
  const resolvedMode = (mode === "system" ? systemMode : mode) ?? "light";

  // The visualizer is served by the ICON backend under /visualizer/ (same
  // origin, see src/icon/server/web_server/visualiser.py) and reads its
  // endpoint configuration from these localStorage keys. Seeding them before
  // the iframe mounts makes it connect to ICON without manual configuration.
  localStorage.setItem("libraryAddress", hostname);
  localStorage.setItem("libraryPort", String(port));

  const iframeParams = new URLSearchParams({
    theme: resolvedMode,
    embedded: "1",
  });
  const jobId = searchParams.get("jobId");
  const datapoint = searchParams.get("datapoint");
  if (jobId) iframeParams.set("jobId", jobId);
  if (datapoint) iframeParams.set("datapoint", datapoint);

  return (
    <iframe
      src={`/visualizer/?${iframeParams.toString()}`}
      title="Sequence Visualizer"
      style={{ display: "block", width: "100%", height: "100%", border: "none" }}
    />
  );
}
