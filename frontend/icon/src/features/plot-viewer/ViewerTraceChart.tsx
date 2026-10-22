import { createContext, useContext, useMemo } from "react";
import type { LineSeriesOption } from "echarts";
import type { ReactEChartsProps } from "../../components/ReactEcharts";
import { ViewerChart } from "./ViewerChart";
export const RepetitionSeriesContext = createContext<LineSeriesOption[]>([]);
export function ViewerTraceChart(props: ReactEChartsProps) {
  const repetitions = useContext(RepetitionSeriesContext);
  const option = useMemo(
    () => ({
      ...props.option,
      series: [...[props.option.series ?? []].flat(), ...repetitions],
    }),
    [props.option, repetitions],
  );
  return <ViewerChart {...props} option={option} />;
}
