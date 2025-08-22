import { ShowNotification } from "@toolpad/core";
import type { ECharts } from "echarts/core";

export async function copyEChartsToClipboard(
  chartRef: React.RefObject<ECharts | null>,
  showNotification: ShowNotification,
) {
  if (!chartRef.current) return;

  const originalToolbox = chartRef.current.getOption().toolbox;
  chartRef.current.setOption({ toolbox: { show: false } });

  const dataUrl = chartRef.current.getDataURL({ pixelRatio: 2 });

  chartRef.current.setOption({ toolbox: originalToolbox });

  const res = await fetch(dataUrl);
  const blob = await res.blob();

  await navigator.clipboard.write([new ClipboardItem({ [blob.type]: blob })]);

  showNotification("Image copied to the clipboard", {
    autoHideDuration: 3000,
    severity: "info",
  });
}
