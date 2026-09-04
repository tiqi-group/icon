import { useEffect, useCallback } from "react";
import { useParams } from "react-router";
import { JobView } from "../components/JobView";
import {
  extractExperimentId,
  extractStorageKey,
  getWindowName,
} from "../utils/windowUtils";

export function JobViewerPage() {
  const { jobId } = useParams();

  const windowName = getWindowName();
  const storageKey = extractStorageKey(windowName);
  const experimentId = extractExperimentId(windowName);

  useEffect(() => {
    if (!storageKey) return;
    if (localStorage.getItem("separateJobWindows") === "true")
      document.title = `Experiment View ${jobId}`;
    else document.title = `Experiment View ${experimentId}`;

    const saveBounds = () => {
      const bounds = {
        width: window.innerWidth,
        height: window.innerHeight,
        top: window.screenTop,
        left: window.screenLeft,
        scrollX: window.scrollX,
        scrollY: window.scrollY,
      };
      localStorage.setItem(storageKey, JSON.stringify(bounds));
    };

    window.addEventListener("beforeunload", saveBounds);
    window.addEventListener("resize", saveBounds);
    window.addEventListener("scroll", saveBounds);

    return () => {
      window.removeEventListener("beforeunload", saveBounds);
      window.removeEventListener("resize", saveBounds);
      window.removeEventListener("scroll", saveBounds);
    };
  }, [storageKey, jobId]);

  const scroll = useCallback(() => {
    if (!storageKey) return;
    const saved = JSON.parse(localStorage.getItem(storageKey) || "{}");
    if (typeof saved.scrollX === "number" && typeof saved.scrollY === "number") {
      window.scrollTo(saved.scrollX, saved.scrollY);
    }
  }, [storageKey]);

  return <JobView jobId={jobId} onLoaded={scroll} />;
}
