import type { ECharts } from "echarts/core";
import type { ShowNotification } from "@toolpad/core";
import { copyEChartsToClipboard } from "./copyEChartsToClipboard";

/**
 * Layout shared by all plots of the job view.
 *
 * Every plot uses the same canvas height and the same header layout, so that
 * neighbouring cards line up and the plot areas start at the same y position:
 *
 *   y  0 .. 20   title (left)                            toolbox (right)
 *   y 20 .. 34   subtitle (left)
 *   y 36 .. 54   legend (centred, scrollable)
 *   y 60 ..      plot area
 *
 * The header is left aligned so that a long title or subtitle is only ever cut
 * off on the right instead of on both sides, and so that it can never collide
 * with the toolbox icons in the top right corner.
 */
export const CHART_HEIGHT = 300;

const COPY_TO_CLIPBOARD_ICON =
  "path://M48.7643 38.2962H100.5807a6.0158 6.0158 0 0 1 6.0158 6.0158V115.2992a6.0158 6.0158 0 0 1-6.0158 6.0158H48.7643a6.0158 6.0158 0 0 1-6.0158-6.0158V44.312a6.0158 6.0158 0 0 1 6.0158-6.0158zM31.3642 21.6047c-3.3328 0-6.0162 2.6829-6.0162 6.0157v70.9874c0 3.3328 2.6834 6.0157 6.0162 6.0157H42.7485V44.3119c0-3.3328 2.6829-6.0157 6.0157-6.0157h40.4322V27.6204c0-3.3328-2.6829-6.0157-6.0157-6.0157z";

export const CHART_TEXT_STYLE = { fontFamily: "sans-serif", fontSize: 12 } as const;

export const chartTitle = (text: string, subtext: string) =>
  ({
    text,
    subtext,
    left: 4,
    top: 2,
    itemGap: 4,
    textStyle: { fontSize: 14, fontWeight: "bold" },
    subtextStyle: { fontSize: 11, lineHeight: 12 },
  }) as const;

export const chartToolbox = (
  chart: ECharts | null,
  showNotification: ShowNotification,
) =>
  ({
    top: 0,
    right: 4,
    itemSize: 14,
    itemGap: 10,
    feature: {
      dataZoom: { yAxisIndex: "none" },
      myCopyToClipboard: {
        show: true,
        title: "Copy to Clipboard",
        icon: COPY_TO_CLIPBOARD_ICON,
        onclick: () => copyEChartsToClipboard(chart, showNotification),
      },
    },
  }) as const;

export const CHART_LEGEND = {
  type: "scroll",
  top: 36,
  left: "center",
  itemHeight: 10,
  textStyle: { fontSize: 11 },
} as const;

export const CHART_GRID = {
  left: 8,
  right: 8,
  bottom: 8,
  top: 60,
  outerBoundsMode: "same",
  outerBoundsContain: "all",
} as const;

/** Axis name placement: the name is kept just outside the tick labels. */
export const CHART_AXIS_NAME = {
  nameLocation: "middle",
  nameGap: 8,
  nameMoveOverlap: true,
} as const;
