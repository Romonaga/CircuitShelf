import type { StatusHistoryPoint } from "../hooks/useStatusHistory";
import { formatNumber } from "../lib/format";

export interface ChartSeries {
  key: keyof StatusHistoryPoint;
  label: string;
  color: string;
}

function numericValues(history: StatusHistoryPoint[], series: ChartSeries[]) {
  return history.flatMap((point) =>
    series
      .map((item) => point[item.key])
      .filter((value): value is number => typeof value === "number" && Number.isFinite(value))
  );
}

function pathForSeries(
  history: StatusHistoryPoint[],
  series: ChartSeries,
  min: number,
  max: number,
  width: number,
  height: number
) {
  const values = history
    .map((point, index) => ({ index, value: point[series.key] }))
    .filter((point): point is { index: number; value: number } => typeof point.value === "number" && Number.isFinite(point.value));
  if (!values.length) {
    return "";
  }
  const denominator = Math.max(max - min, 1);
  return values
    .map(({ index, value }, pathIndex) => {
      const x = history.length <= 1 ? 0 : (index / (history.length - 1)) * width;
      const y = height - ((value - min) / denominator) * height;
      return `${pathIndex === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    })
    .join(" ");
}

export function PerformanceChart({
  title,
  subtitle,
  history,
  series,
  fixedMin,
  fixedMax,
  unit = ""
}: {
  title: string;
  subtitle: string;
  history: StatusHistoryPoint[];
  series: ChartSeries[];
  fixedMin?: number;
  fixedMax?: number;
  unit?: string;
}) {
  const width = 760;
  const height = 250;
  const values = numericValues(history, series);
  const min = fixedMin ?? Math.min(0, ...values);
  const rawMax = fixedMax ?? Math.max(10, ...values);
  const max = rawMax === min ? min + 1 : rawMax;
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
      <svg className="performance-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={title}>
        {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
          <g key={ratio}>
            <line x1="0" x2={width} y1={height * ratio} y2={height * ratio} />
            <text x="0" y={Math.max(11, height * ratio - 5)}>
              {formatNumber(max - (max - min) * ratio)}{unit}
            </text>
          </g>
        ))}
        {series.map((item) => {
          const path = pathForSeries(history, item, min, max, width, height);
          return path ? <path key={item.label} d={path} stroke={item.color} /> : null;
        })}
      </svg>
      <div className="chart-legend">
        {series.map((item) => (
          <span key={item.label}>
            <i style={{ background: item.color }} />
            {item.label}
            <strong>{latest ? formatNumber(latest[item.key] as number | null) : "n/a"}{unit}</strong>
          </span>
        ))}
      </div>
    </section>
  );
}
