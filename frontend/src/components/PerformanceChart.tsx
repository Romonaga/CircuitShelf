import { lazy, Suspense } from "react";
import type { StatusHistoryPoint } from "../libs/performance/history";
import { formatNumber } from "../libs/format";

const EChartsLineChart = lazy(() => import("./EChartsLineChart").then((module) => ({ default: module.EChartsLineChart })));

export interface ChartSeries {
  key: keyof StatusHistoryPoint;
  label: string;
  color: string;
  lineType?: "solid" | "dashed" | "dotted";
  symbol?: "circle" | "rect" | "roundRect" | "triangle" | "diamond";
}

function swatchBackground(color: string, lineType: ChartSeries["lineType"] = "solid") {
  if (lineType === "dashed") {
    return `repeating-linear-gradient(90deg, ${color} 0 8px, transparent 8px 13px)`;
  }
  if (lineType === "dotted") {
    return `repeating-linear-gradient(90deg, ${color} 0 3px, transparent 3px 8px)`;
  }
  return color;
}

function numericValues(history: StatusHistoryPoint[], series: ChartSeries[]) {
  return history.flatMap((point) =>
    series
      .map((item) => point[item.key])
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  );
}

function formatTooltipDate(value: number) {
  return new Date(value).toLocaleString();
}

export function PerformanceChart({
  title,
  subtitle,
  history,
  series,
  fixedMin,
  fixedMax,
  topPaddingRatio = fixedMax === 100 ? 0.25 : 0.06,
  unit = ""
}: {
  title: string;
  subtitle: string;
  history: StatusHistoryPoint[];
  series: ChartSeries[];
  fixedMin?: number;
  fixedMax?: number;
  topPaddingRatio?: number;
  unit?: string;
}) {
  const values = numericValues(history, series);
  const min = fixedMin ?? Math.min(0, ...values);
  const rawMax = fixedMax ?? Math.max(10, ...values);
  const range = rawMax - min;
  const paddedMax = rawMax + Math.max(range || 1, 1) * topPaddingRatio;
  const max = rawMax === min ? min + 1 : paddedMax;
  const labelMax = fixedMax === 100 && unit === "%" ? 100 : undefined;
  const ceiling = labelMax === 100 ? 100 : undefined;
  const latest = history[history.length - 1];

  return (
    <section className="performance-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>{title}</h3>
          <p>{subtitle}</p>
        </div>
        <span>{history.length} samples</span>
      </div>
      <Suspense fallback={<div className="performance-echart loading-chart">Loading chart...</div>}>
        <EChartsLineChart
          title={title}
          history={history}
          series={series}
          min={min}
          max={max}
          unit={unit}
          labelMax={labelMax}
          ceiling={ceiling}
        />
      </Suspense>
      <div className="chart-legend">
        {series.map((item) => (
          <span key={item.label}>
            <i
              className={item.lineType ? `chart-swatch-${item.lineType}` : undefined}
              style={{ background: swatchBackground(item.color, item.lineType) }}
            />
            {item.label}
            <strong>{latest ? formatNumber(latest[item.key] as number | null) : "n/a"}{unit}</strong>
          </span>
        ))}
        {latest ? <small className="chart-latest-time">Latest {formatTooltipDate(latest.sampledAt)}</small> : null}
      </div>
    </section>
  );
}
