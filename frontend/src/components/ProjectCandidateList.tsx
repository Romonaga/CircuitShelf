import type { ProjectCandidate } from "../types";
import { formatNumber } from "../lib/format";

export function ProjectCandidateList({
  candidates,
  finding,
  buildingId,
  onBuild
}: {
  candidates: ProjectCandidate[];
  finding: boolean;
  buildingId: string;
  onBuild: (candidate: ProjectCandidate) => void;
}) {
  if (finding && !candidates.length) {
    return <div className="empty-state compact">Finding buildable projects...</div>;
  }

  if (!candidates.length) {
    return <div className="empty-state compact">Run the finder after adding parts.</div>;
  }

  return (
    <div className="project-candidate-list">
      {candidates.map((candidate) => (
        <article key={candidate.id} className={candidate.buildable ? "project-candidate buildable" : "project-candidate"}>
          <div className="project-candidate-heading">
            <div>
              <h3>{candidate.title}</h3>
              <p>
                {candidate.displayName}
                {candidate.page ? ` | page ${candidate.page}` : ""} | score {formatNumber(candidate.score)}
              </p>
            </div>
            <span className={candidate.buildable ? "status-pill ok" : "status-pill warn"}>
              {candidate.buildable ? "Buildable" : `${candidate.missingParts.length} missing`}
            </span>
          </div>
          <p className="project-candidate-summary">{candidate.summary}</p>
          <div className="project-part-columns">
            <PartPillGroup title="Owned" parts={candidate.matchedParts.map((part) => part.displayName || part.name || "")} />
            <PartPillGroup title="Missing" parts={candidate.missingParts.map((part) => part.name || part.displayName || "")} />
          </div>
          <button className="primary-button compact-button" disabled={Boolean(buildingId)} onClick={() => onBuild(candidate)}>
            {buildingId === candidate.id ? "Creating..." : "Create Bench plan"}
          </button>
        </article>
      ))}
    </div>
  );
}

function PartPillGroup({ title, parts }: { title: string; parts: string[] }) {
  return (
    <div className="project-part-group">
      <strong>{title}</strong>
      <div>
        {parts.length ? parts.map((part) => <span key={part}>{part}</span>) : <small>None detected</small>}
      </div>
    </div>
  );
}
