import type { PerformanceWorkRun } from "../types";
import { formatNumber } from "../lib/format";
import { chartColors } from "../lib/chartColors";

interface ThroughputRow {
  id: number | string;
  label: string;
  chunksPerMinute: number;
  imagesPerMinute: number;
}

function throughputRows(rows: PerformanceWorkRun[]): ThroughputRow[] {
  return rows
    .filter((row) => row.durationMs > 0 && (row.chunks > 0 || row.images > 0))
    .slice(0, 12)
    .map((row) => {
      const minutes = Math.max(row.durationMs / 60000, 0.001);
      return {
        id: row.id,
        label: row.label || row.sourcePath || row.workTypeLabel,
        chunksPerMinute: row.chunks / minutes,
        imagesPerMinute: row.images / minutes
      };
    });
}

export function IngestionThroughputChart({ rows }: { rows: PerformanceWorkRun[] }) {
  const data = throughputRows(rows);
  const max = Math.max(1, ...data.flatMap((row) => [row.chunksPerMinute, row.imagesPerMinute]));
  return (
    <section className="performance-chart-card work-chart-card">
      <div className="performance-chart-heading">
        <div>
          <h3>Ingestion throughput</h3>
          <p>Chunks and image assets per minute for recent document work.</p>
        </div>
        <span>{data.length} jobs</span>
      </div>
      {data.length ? (
        <div className="throughput-bars">
          {data.map((row) => (
            <div key={row.id} className="throughput-row">
              <strong title={row.label}>{row.label}</strong>
              <div>
                <span className="mini-label">Chunks</span>
                <i style={{ width: `${Math.max(2, (row.chunksPerMinute / max) * 100)}%`, background: chartColors.green }} />
                <b>{formatNumber(row.chunksPerMinute)}/min</b>
              </div>
              <div>
                <span className="mini-label">Images</span>
                <i style={{ width: `${Math.max(2, (row.imagesPerMinute / max) * 100)}%`, background: chartColors.orange }} />
                <b>{formatNumber(row.imagesPerMinute)}/min</b>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="empty-state">No throughput data yet. It will appear after document ingestion work completes.</p>
      )}
    </section>
  );
}
