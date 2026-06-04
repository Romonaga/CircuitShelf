import { useEffect, useMemo } from "react";
import type { StatusHistoryPoint } from "../hooks/useStatusHistory";
import type { ChartSeries } from "./PerformanceChart";
import { useEChart } from "../hooks/charts/useEChart";
import { buildLineChartOption, type LineChartOption } from "../libs/performanceCharts/lineChartOption";

export function EChartsLineChart({
  title,
  history,
  series,
  min,
  max,
  unit,
  labelMax,
  ceiling
}: {
  title: string;
  history: StatusHistoryPoint[];
  series: ChartSeries[];
  min: number;
  max: number;
  unit: string;
  labelMax?: number;
  ceiling?: number;
}) {
  const { chartRef, setOption, theme } = useEChart<LineChartOption>();
  const option = useMemo<LineChartOption>(
    () => buildLineChartOption({ history, series, min, max, unit, labelMax, ceiling, theme }),
    [ceiling, history, labelMax, max, min, series, theme, unit]
  );

  useEffect(() => {
    setOption(option);
  }, [option, setOption]);

  return <div ref={chartRef} className="performance-echart" role="img" aria-label={title} />;
}
