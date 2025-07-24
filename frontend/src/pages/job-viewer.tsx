import { useEffect, useCallback } from "react";
import { useParams } from "react-router";
import { JobView } from "../components/JobView";
import { extractStorageKey, getWindowName } from "../utils/windowUtils";

export function JobViewerPage() {
  const { jobId } = useParams();

  const windowName = getWindowName();
  const storageKey = extractStorageKey(windowName);

  const saveBounds = useCallback(() => {
    if (!storageKey) return;
    const bounds = {
      width: window.outerWidth,
      height: window.outerHeight,
      top: window.screenTop,
      left: window.screenLeft,
    };
    localStorage.setItem(storageKey, JSON.stringify(bounds));
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey) return;
    document.title = `ICON - Experiment View ${jobId}`;

    window.addEventListener("beforeunload", saveBounds);
    window.addEventListener("resize", saveBounds);

    return () => {
      window.removeEventListener("beforeunload", saveBounds);
      window.removeEventListener("resize", saveBounds);
    };
  }, [saveBounds, storageKey, jobId]);

  return <JobView jobId={jobId} />;
}
