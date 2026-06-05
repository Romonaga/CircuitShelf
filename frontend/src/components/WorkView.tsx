import { useState } from "react";
import type { StatusPayload } from "../types";
import { usePerformanceReport } from "../hooks/usePerformanceReport";
import { LoadingSpinner } from "./LoadingSpinner";
import { RecentWorkTable } from "./RecentWorkTable";
import { SectionHeader } from "./SectionHeader";

export function WorkView({
  isActive,
  status
}: {
  isActive: boolean;
  status: StatusPayload | null;
}) {
  const [showIndexChecks, setShowIndexChecks] = useState(false);
  const report = usePerformanceReport(isActive, 24, status?.ingest?.lastFinishedAt ?? "");
  const recentWork = report.report?.recentWork ?? [];
  const visibleRecentWork = showIndexChecks ? recentWork : recentWork.filter((row) => row.workType !== "index_check");
  const initialLoad = report.loading && !report.report;

  return (
    <section className="performance-page work-page">
      <SectionHeader
        title="Work"
        description="Completed ingestion runs, checks, AI calls, and measured background work."
        actions={
          <button className="ghost-button" type="button" onClick={() => void report.refresh()} disabled={report.loading}>
            {report.loading ? "Refreshing..." : "Refresh"}
          </button>
        }
      />
      {report.error ? <p className="error">{report.error}</p> : null}
      {report.loading ? (
        <div className="performance-loading-banner" role="status" aria-live="polite">
          <LoadingSpinner />
          <div>
            <strong>{initialLoad ? "Loading work history" : "Refreshing work history"}</strong>
            <span>Pulling persisted work runs and token/cost details.</span>
          </div>
        </div>
      ) : null}
      <RecentWorkTable rows={visibleRecentWork} showIndexChecks={showIndexChecks} onShowIndexChecksChange={setShowIndexChecks} />
    </section>
  );
}
