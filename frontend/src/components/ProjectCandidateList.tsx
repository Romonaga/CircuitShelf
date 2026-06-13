import type { ProjectCandidate } from "../types";
import { ProjectCandidateCard } from "./projectFinder/ProjectCandidateCard";

export function ProjectCandidateList({
  candidates,
  finding,
  emptyLabel = "Run the finder after adding parts.",
  buildingId,
  buildingElapsedSeconds,
  onBuild
}: {
  candidates: ProjectCandidate[];
  finding: boolean;
  emptyLabel?: string;
  buildingId: string;
  buildingElapsedSeconds: number;
  onBuild: (candidate: ProjectCandidate) => void;
}) {
  if (finding && !candidates.length) {
    return <div className="empty-state compact">Finding buildable projects...</div>;
  }

  if (!candidates.length) {
    return <div className="empty-state compact">{emptyLabel}</div>;
  }

  return (
    <div className="project-candidate-list">
      {candidates.map((candidate) => (
        <ProjectCandidateCard
          key={candidate.id}
          candidate={candidate}
          building={buildingId === candidate.id}
          buildingElapsedSeconds={buildingElapsedSeconds}
          disabled={Boolean(buildingId)}
          onBuild={onBuild}
        />
      ))}
    </div>
  );
}
