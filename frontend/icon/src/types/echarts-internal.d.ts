// Internal echarts module used to keep the toolbox zoom history alive across
// setOption({ notMerge: true }) calls (each of which builds a new GlobalModel).
declare module "echarts/lib/component/dataZoom/history.js" {
  export interface DataZoomStoreSnapshotItem {
    dataZoomId?: string;
    start?: number;
    end?: number;
    startValue?: number;
    endValue?: number;
  }

  // ecModel is the chart's internal GlobalModel (chart.getModel()).
  export function push(
    ecModel: unknown,
    newSnapshot: Record<string, DataZoomStoreSnapshotItem>,
  ): void;
}
