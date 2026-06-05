import { useState } from "react";
import type { StatusPayload } from "../types";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { usePerformanceHistory } from "../hooks/charts/usePerformanceHistory";
import { LoadingSpinner } from "./LoadingSpinner";
import { SectionHeader } from "./SectionHeader";
import { PerformanceChartDeck } from "./performance/PerformanceChartDeck";
import { PerformanceChartSelector } from "./performance/PerformanceChartSelector";
import { PerformanceStatsGrid } from "./performance/PerformanceStatsGrid";
import { LiveResourcePressure } from "./performance/LiveResourcePressure";
import type { PerformanceChartChoice } from "./performance/chartTypes";

export function PerformanceView({
  status,
  isActive
}: {
  status: StatusPayload | null;
  isActive: boolean;
}) {
  const report = usePerformanceReport(isActive, 24, status?.ingest?.lastFinishedAt ?? "");
  const [chartChoice, setChartChoice] = useState<PerformanceChartChoice>("utilization");
  const resources = status?.systemResources;
  const runtimePeaks = resources?.peaks;
  const { history, peaks } = usePerformanceHistory({
    isActive,
    status,
    reportSamples: report.report?.samples,
  });
  const peakWorkers = Math.max(runtimePeaks?.activeDocumentWorkers ?? 0, peaks.workers ?? 0);
  const recentWork = report.report?.recentWork ?? [];
  const chartWorkRows = recentWork.filter((row) => row.workType !== "index_check");
  const initialPerformanceLoad = report.loading && !report.report;

  return (
    <section className="performance-page">
      <SectionHeader
        title="Performance"
        description="Runtime load, ingestion progress, GPU sizing, and completed work output."
      />
      {report.error ? <p className="error">{report.error}</p> : null}
      {report.loading ? (
        <div className="performance-loading-banner" role="status" aria-live="polite">
          <LoadingSpinner />
          <div>
            <strong>{initialPerformanceLoad ? "Loading performance history" : "Refreshing performance history"}</strong>
            <span>Live status keeps updating while the historical samples and work runs load.</span>
          </div>
        </div>
      ) : null}

      <PerformanceStatsGrid resources={resources} peaks={peaks} peakWorkers={peakWorkers} />
      <LiveResourcePressure resources={resources} />

      <div className="performance-chart-workspace">
        <PerformanceChartSelector value={chartChoice} onChange={setChartChoice} />
        <PerformanceChartDeck
          chartChoice={chartChoice}
          history={history}
          visibleRecentWork={chartWorkRows}
          loadingInitial={initialPerformanceLoad}
        />
      </div>
    </section>
  );
}
