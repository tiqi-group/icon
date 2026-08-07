import { useColorScheme } from "@mui/material/styles";
import { hostname, port } from "../socket";

export function VisualiserPage() {
  const { mode, systemMode } = useColorScheme();
  const resolvedMode = (mode === "system" ? systemMode : mode) ?? "light";

  // The visualiser is served by the ICON backend under /visualiser/ (same
  // origin, see src/icon/server/web_server/visualiser.py) and reads its
  // endpoint configuration from these localStorage keys. Seeding them before
  // the iframe mounts makes it connect to ICON without manual configuration.
  localStorage.setItem("libraryAddress", hostname);
  localStorage.setItem("libraryPort", String(port));

  return (
    <iframe
      src={`/visualiser/?theme=${resolvedMode}`}
      title="Sequence Visualiser"
      style={{ display: "block", width: "100%", height: "100%", border: "none" }}
    />
  );
}
