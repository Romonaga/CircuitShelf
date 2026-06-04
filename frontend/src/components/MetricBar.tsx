import { formatPercent } from "../libs/format";

export function MetricBar({
  label,
  value,
  detail,
  tone = "teal",
  max = 100
}: {
  label: string;
  value?: number | null;
  detail?: string;
  tone?: "teal" | "orange" | "blue" | "green";
  max?: number;
}) {
  const numeric = Number.isFinite(value ?? NaN) ? Number(value) : 0;
  const width = Math.max(0, Math.min((numeric / max) * 100, 100));
  return (
    <div className="metric-bar">
      <div className="metric-bar-label">
        <span>{label}</span>
        <strong>{detail ?? formatPercent(value)}</strong>
      </div>
      <div className="metric-bar-track">
        <span className={`metric-bar-fill ${tone}`} style={{ width: `${width}%` }} />
      </div>
    </div>
  );
}
