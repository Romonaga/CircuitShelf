import type { ProjectCandidate, ProjectCandidatePart } from "../../types";
import { formatNumber } from "../../libs/format";
import { formatElapsed } from "../../libs/time";
import { LoadingSpinner } from "../LoadingSpinner";

export function ProjectCandidateCard({
  candidate,
  building,
  buildingElapsedSeconds,
  disabled,
  onBuild
}: {
  candidate: ProjectCandidate;
  building: boolean;
  buildingElapsedSeconds: number;
  disabled: boolean;
  onBuild: (candidate: ProjectCandidate) => void;
}) {
  const missingLabel = candidate.missingParts.length === 1 ? "1 gap" : `${candidate.missingParts.length} gaps`;
  const duplicateLabel = candidate.dedupeCount && candidate.dedupeCount > 1 ? `${candidate.dedupeCount} similar hits merged` : "";

  return (
    <article className={candidate.buildable ? "project-candidate buildable" : "project-candidate"}>
      <div className="project-candidate-heading">
        <div>
          <h3>{candidate.title}</h3>
          <p>
            {candidate.displayName}
            {candidate.page ? ` | page ${candidate.page}` : ""} | score {formatNumber(candidate.score)}
            {duplicateLabel ? ` | ${duplicateLabel}` : ""}
          </p>
        </div>
        <span className={candidate.buildable ? "status-pill ok" : "status-pill warn"}>
          {candidate.buildable ? "Buildable" : missingLabel}
        </span>
      </div>

      <p className="project-candidate-summary">{candidate.summary}</p>

      <div className="project-part-columns three">
        <PartPillGroup title="Inventory match" parts={candidate.matchedParts} emptyLabel="No inventory match" mode="owned" />
        <PartPillGroup title="Source requires" parts={candidate.requiredParts} emptyLabel="No parts inferred" mode="required" />
        <PartPillGroup title="Needs attention" parts={candidate.missingParts} emptyLabel="No unresolved parts" mode="missing" />
      </div>

      <CandidateEvidence candidate={candidate} />

      <button className="primary-button compact-button" disabled={disabled} onClick={() => onBuild(candidate)}>
        {building ? (
          <>
            <LoadingSpinner className="button-spinner" />
            Creating {formatElapsed(buildingElapsedSeconds)}
          </>
        ) : (
          "Create Bench plan"
        )}
      </button>
    </article>
  );
}

function CandidateEvidence({ candidate }: { candidate: ProjectCandidate }) {
  const hasEvidence =
    candidate.suggestedSubstitutions.length ||
    candidate.matchReasons?.length ||
    candidate.missingReasons?.length ||
    candidate.rejectionReasons?.length;
  if (!hasEvidence) {
    return null;
  }
  return (
    <div className="project-candidate-evidence">
      {candidate.suggestedSubstitutions.length ? (
        <EvidenceGroup
          title="Alias substitutions"
          items={candidate.suggestedSubstitutions.map((item) => `${item.required} -> ${item.use}: ${item.reason}`)}
        />
      ) : null}
      <EvidenceGroup title="Matches" items={candidate.matchReasons || []} />
      <EvidenceGroup title="Open questions" items={candidate.missingReasons || []} />
      <EvidenceGroup title="Candidate caveats" items={candidate.rejectionReasons || []} />
    </div>
  );
}

function EvidenceGroup({ title, items }: { title: string; items: string[] }) {
  if (!items.length) {
    return null;
  }
  return (
    <div className="project-evidence-group">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function PartPillGroup({
  title,
  parts,
  emptyLabel,
  mode
}: {
  title: string;
  parts: ProjectCandidatePart[];
  emptyLabel: string;
  mode: "owned" | "required" | "missing";
}) {
  return (
    <div className={`project-part-group ${mode}`}>
      <strong>{title}</strong>
      <div>
        {parts.length ? (
          parts.map((part) => <PartPill key={`${part.id || part.name || part.displayName}-${part.type || part.partType}`} part={part} />)
        ) : (
          <small>{emptyLabel}</small>
        )}
      </div>
    </div>
  );
}

function PartPill({ part }: { part: ProjectCandidatePart }) {
  const label = part.displayName || part.name || "Unknown part";
  const detail = part.location || part.reason || part.type || part.partType || "";
  return (
    <span title={detail || label}>
      {label}
      {detail ? <small>{detail}</small> : null}
    </span>
  );
}
