import { ShowNotification } from "@toolpad/core";
import type { ECharts } from "echarts/core";

export async function copyEChartsToClipboard(
  chart: ECharts | null,
  showNotification: ShowNotification,
) {
  if (!chart) return;

  const originalToolbox = chart.getOption().toolbox;
  chart.setOption({ toolbox: { show: false } });

  const dataUrl = chart.getDataURL({ pixelRatio: 2 });

  chart.setOption({ toolbox: originalToolbox });

  const [header, b64] = dataUrl.split(",");
  const mimeType = header.match(/:(.*?);/)?.[1] ?? "image/png";
  const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
  const blob = new Blob([bytes], { type: mimeType });

  // navigator.clipboard requires a secure context (HTTPS / localhost).
  if (!navigator.clipboard) {
    showNotification(
      "ICON needs to be served via HTTPS for copy to clipboard",
      { autoHideDuration: 5000, severity: "error" },
    );
    return;
  }

  try {
    // Blob is created synchronously above so clipboard.write() stays within
    // the user gesture context — async fetch() would expire it in Chrome.
    await navigator.clipboard.write([new ClipboardItem({ [mimeType]: blob })]);
    showNotification("Image copied to the clipboard", {
      autoHideDuration: 3000,
      severity: "info",
    });
  } catch (err) {
    console.error("[copyEChartsToClipboard] clipboard.write failed:", err);
    showNotification("Failed to copy image to clipboard", {
      autoHideDuration: 4000,
      severity: "error",
    });
  }
}
