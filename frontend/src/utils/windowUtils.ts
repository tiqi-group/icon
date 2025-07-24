import { authority, forwardedProto } from "../socket";

export function openJobWindow(jobId: string | number, experimentId: string) {
  const baseUrl = `${forwardedProto}://${authority}`;
  const url = `${baseUrl}/data/${jobId}`;
  const storageKey = `jobWindow:${experimentId}`;

  const storedWindowSettings = JSON.parse(localStorage.getItem(storageKey) || "{}");
  const features = `toolbar=no,location=no,status=no,menubar=no,scrollbars=no,resizable=yes,
    width=${storedWindowSettings.width || 600},
    height=${storedWindowSettings.height || 500},
    left=${storedWindowSettings.left || 100},
    top=${storedWindowSettings.top || 100}`;

  let separateJobWindows = localStorage.getItem("separateJobWindows");
  if (separateJobWindows === null) {
    const result = window.confirm(
      "Should jobs reuse one window per experiment?\n\n" +
        "You can change this later in Settings > Browser > Use separate job windows.",
    );
    separateJobWindows = result ? "false" : "true";
    localStorage.setItem("separateJobWindows", separateJobWindows);
  }

  const useSeparate = separateJobWindows === "true";
  const windowName = useSeparate ? `${storageKey}:${jobId}` : storageKey;

  window.open(url, windowName, features);
}

export function extractStorageKey(windowName: string): string | null {
  const prefix = "jobWindow:";
  if (!windowName.startsWith(prefix)) return null;

  const parts = windowName.split(":");
  const hasJobId = parts.length > 2;

  return hasJobId ? parts.slice(0, -1).join(":") : windowName;
}

export function extractExperimentId(windowName: string): string | null {
  const prefix = "jobWindow:";
  if (!windowName.startsWith(prefix)) return null;

  const parts = windowName.split(":");

  return parts[1];
}

export function getWindowName(): string {
  return window.name || document.title;
}
