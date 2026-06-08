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

  try {
    // Convert synchronously so clipboard.write() stays within the user gesture.
    // Using fetch() on a data URL introduces async awaits that can expire the
    // gesture context in Chrome, causing a silent NotAllowedError.
    const [header, b64] = dataUrl.split(",");
    const mimeType = header.match(/:(.*?);/)?.[1] ?? "image/png";
    const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
    const blob = new Blob([bytes], { type: mimeType });

    await navigator.clipboard.write([new ClipboardItem({ [mimeType]: blob })]);
    showNotification("Image copied to the clipboard", {
      autoHideDuration: 3000,
      severity: "info",
    });
  } catch {
    showNotification("Failed to copy image to clipboard", {
      autoHideDuration: 4000,
      severity: "error",
    });
  }
}
