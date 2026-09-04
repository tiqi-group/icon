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

  const res = await fetch(dataUrl);
  const blob = await res.blob();

  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);

  showNotification("Image copied to the clipboard", {
    autoHideDuration: 3000,
    severity: "info",
  });
}
