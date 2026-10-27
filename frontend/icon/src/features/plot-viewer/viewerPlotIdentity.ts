import { createContext } from "react";

export interface ViewerPlotIdentity {
  title: string;
  subtitle: string;
}

export const ViewerPlotIdentityContext = createContext<ViewerPlotIdentity | null>(null);

/** Keep scheduled time verbatim (including its offset), as an experiment identifier. */
export function viewerPlotIdentity(
  plotName: string,
  jobId: string,
  deviceId: string,
  experimentName?: string,
  scheduledTime?: string,
): ViewerPlotIdentity {
  return {
    title: `${plotName} · Job ${jobId}`,
    subtitle: [
      [experimentName, deviceId].filter(Boolean).join(" · "),
      scheduledTime?.replace("T", " "),
    ]
      .filter(Boolean)
      .join("\n"),
  };
}
