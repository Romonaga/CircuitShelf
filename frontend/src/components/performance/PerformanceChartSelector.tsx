import type { PerformanceChartChoice } from "./chartTypes";

export function PerformanceChartSelector({
  value,
  onChange
}: {
  value: PerformanceChartChoice;
  onChange: (value: PerformanceChartChoice) => void;
}) {
  return (
    <div className="chart-toolbar">
      <label>
        <span>Graph</span>
        <select value={value} onChange={(event) => onChange(event.target.value as PerformanceChartChoice)}>
          <option value="utilization">Utilization</option>
          <option value="gpuEnvelope">GPU envelope</option>
          <option value="gpuQueue">GPU queue pressure</option>
          <option value="thermals">Thermals</option>
          <option value="power">Power</option>
          <option value="documentOutput">Document output</option>
          <option value="workers">Workers and CUDA batches</option>
          <option value="ingestionWork">Ingestion work health</option>
          <option value="all">All charts</option>
        </select>
      </label>
    </div>
  );
}
