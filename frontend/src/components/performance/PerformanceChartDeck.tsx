import type { StatusHistoryPoint } from "../../hooks/useStatusHistory";
import type { PerformanceWorkRun } from "../../types";
import { IngestionThroughputChart } from "../IngestionThroughputChart";
import { LoadingSpinner } from "../LoadingSpinner";
import { WorkDurationChart } from "../WorkDurationChart";
import { BatchEfficiencyGraph } from "../performanceCharts/BatchEfficiencyGraph";
import { DocumentOutputGraph } from "../performanceCharts/DocumentOutputGraph";
import { GpuEnvelopeGraph } from "../performanceCharts/GpuEnvelopeGraph";
import { IngestionOutcomeGraph } from "../performanceCharts/IngestionOutcomeGraph";
import { PowerGraph } from "../performanceCharts/PowerGraph";
import { ThermalGraph } from "../performanceCharts/ThermalGraph";
import { UtilizationGraph } from "../performanceCharts/UtilizationGraph";
import { WorkerBatchGraph } from "../performanceCharts/WorkerBatchGraph";
import type { PerformanceChartChoice } from "./chartTypes";

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
      {showChart("utilization") ? <UtilizationGraph history={history} /> : null}
      {showChart("gpuEnvelope") ? <GpuEnvelopeGraph history={history} /> : null}
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
    </>
  );
}
