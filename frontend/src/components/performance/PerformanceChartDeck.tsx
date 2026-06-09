import { lazy, Suspense } from "react";
import type { StatusHistoryPoint } from "../../libs/performance/history";
import type { PerformanceWorkRun } from "../../types";
import { LoadingSpinner } from "../LoadingSpinner";
import type { PerformanceChartChoice } from "./chartTypes";

const BatchEfficiencyGraph = lazy(() => import("../performanceCharts/BatchEfficiencyGraph").then((module) => ({ default: module.BatchEfficiencyGraph })));
const DocumentOutputGraph = lazy(() => import("../performanceCharts/DocumentOutputGraph").then((module) => ({ default: module.DocumentOutputGraph })));
const GpuEnvelopeGraph = lazy(() => import("../performanceCharts/GpuEnvelopeGraph").then((module) => ({ default: module.GpuEnvelopeGraph })));
const GpuQueueGraph = lazy(() => import("../performanceCharts/GpuQueueGraph").then((module) => ({ default: module.GpuQueueGraph })));
const IngestionOutcomeGraph = lazy(() => import("../performanceCharts/IngestionOutcomeGraph").then((module) => ({ default: module.IngestionOutcomeGraph })));
const IngestionThroughputChart = lazy(() => import("../IngestionThroughputChart").then((module) => ({ default: module.IngestionThroughputChart })));
const PowerGraph = lazy(() => import("../performanceCharts/PowerGraph").then((module) => ({ default: module.PowerGraph })));
const ThermalGraph = lazy(() => import("../performanceCharts/ThermalGraph").then((module) => ({ default: module.ThermalGraph })));
const UtilizationGraph = lazy(() => import("../performanceCharts/UtilizationGraph").then((module) => ({ default: module.UtilizationGraph })));
const WorkerBatchGraph = lazy(() => import("../performanceCharts/WorkerBatchGraph").then((module) => ({ default: module.WorkerBatchGraph })));
const WorkDurationChart = lazy(() => import("../WorkDurationChart").then((module) => ({ default: module.WorkDurationChart })));

export function PerformanceChartDeck({
  chartChoice,
  history,
  visibleRecentWork,
  loadingInitial
}: {
  chartChoice: PerformanceChartChoice;
  history: StatusHistoryPoint[];
  visibleRecentWork: PerformanceWorkRun[];
  loadingInitial: boolean;
}) {
  const showChart = (choice: PerformanceChartChoice) => chartChoice === "all" || chartChoice === choice;

  return (
    <>
      {loadingInitial && history.length === 0 ? (
        <section className="performance-chart-card performance-report-loading">
          <LoadingSpinner />
          <div>
            <h3>Preparing charts</h3>
            <p>Fetching persisted resource samples, recent work runs, and chart modules.</p>
          </div>
        </section>
      ) : null}
      <Suspense fallback={<ChartModuleLoading />}>
        {showChart("utilization") ? <UtilizationGraph history={history} /> : null}
        {showChart("gpuEnvelope") ? <GpuEnvelopeGraph history={history} /> : null}
        {showChart("gpuQueue") ? <GpuQueueGraph history={history} /> : null}
        {showChart("thermals") ? <ThermalGraph history={history} /> : null}
        {showChart("power") ? <PowerGraph history={history} /> : null}
        {showChart("documentOutput") ? <DocumentOutputGraph rows={visibleRecentWork} /> : null}
        {showChart("workers") ? <WorkerBatchGraph history={history} /> : null}
        {showChart("workers") ? <BatchEfficiencyGraph history={history} /> : null}
        {showChart("ingestionWork") ? (
          <>
            <IngestionOutcomeGraph rows={visibleRecentWork} />
            <IngestionThroughputChart rows={visibleRecentWork} />
            <WorkDurationChart rows={visibleRecentWork} />
          </>
        ) : null}
      </Suspense>
    </>
  );
}

function ChartModuleLoading() {
  return (
    <section className="performance-chart-card performance-report-loading">
      <LoadingSpinner />
      <div>
        <h3>Loading chart module</h3>
        <p>Preparing the selected performance visualization.</p>
      </div>
    </section>
  );
}
