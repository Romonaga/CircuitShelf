import { useState } from "react";
import type { StatusPayload } from "../types";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { usePerformanceHistory } from "../hooks/charts/usePerformanceHistory";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { RecentWorkTable } from "./RecentWorkTable";
import { RuntimeBatchPanel } from "./RuntimeBatchPanel";
import { SectionHeader } from "./SectionHeader";
import { PerformanceChartDeck } from "./performance/PerformanceChartDeck";
import { PerformanceChartSelector } from "./performance/PerformanceChartSelector";
import { PerformanceStatsGrid } from "./performance/PerformanceStatsGrid";
import { LiveResourcePressure } from "./performance/LiveResourcePressure";
import type { PerformanceChartChoice } from "./performance/chartTypes";

export function PerformanceView({
  status,
  isActive,
  onOpenReview
}: {
  status: StatusPayload | null;
  isActive: boolean;
  onOpenReview: () => void;
}) {
  const report = usePerformanceReport(isActive, 24, status?.ingest?.lastFinishedAt ?? "");
  const [chartChoice, setChartChoice] = useState<PerformanceChartChoice>("utilization");
  const [showIndexChecks, setShowIndexChecks] = useState(false);
  const resources = status?.systemResources;
  const runtimePeaks = resources?.peaks;
  const { history, peaks } = usePerformanceHistory({
    isActive,
    status,
    reportSamples: report.report?.samples,
  });
  const peakWorkers = Math.max(runtimePeaks?.activeDocumentWorkers ?? 0, peaks.workers ?? 0);
  const recentWork = report.report?.recentWork ?? [];
  const visibleRecentWork = showIndexChecks ? recentWork : recentWork.filter((row) => row.workType !== "index_check");
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

      <div className="performance-layout">
        <div className="performance-main">
          <PerformanceChartSelector value={chartChoice} onChange={setChartChoice} />
          <PerformanceChartDeck
            chartChoice={chartChoice}
            history={history}
            visibleRecentWork={visibleRecentWork}
            loadingInitial={initialPerformanceLoad}
          />
        </div>
        <aside className="performance-side">
          <RuntimeBatchPanel batches={status?.runtimeBatches} />
          <IngestStatusPanel
            ingest={status?.ingest}
            workerBudget={status?.ingestWorkerBudget}
            runtimeBatches={status?.runtimeBatches}
            pendingReview={status?.pendingReview}
            onOpenReview={onOpenReview}
          />
        </aside>
      </div>
      <RecentWorkTable rows={visibleRecentWork} showIndexChecks={showIndexChecks} onShowIndexChecksChange={setShowIndexChecks} />
    </section>
  );
}
