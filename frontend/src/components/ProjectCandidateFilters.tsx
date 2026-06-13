import type { ProjectCandidateFilter } from "../types";
import { LoadingSpinner } from "./LoadingSpinner";

const filters: Array<{ id: ProjectCandidateFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "buildable", label: "Buildable" },
  { id: "needs-parts", label: "Needs parts" }
];

export function ProjectCandidateFilters({
  active,
  counts,
  loading,
  onChange
}: {
  active: ProjectCandidateFilter;
  counts: Record<ProjectCandidateFilter, number>;
  loading?: boolean;
  onChange: (filter: ProjectCandidateFilter) => void;
}) {
  return (
    <div className="project-candidate-filters" aria-label="Project candidate filters">
      {filters.map((filter) => (
        <button
          key={filter.id}
          type="button"
          className={active === filter.id ? "active" : ""}
          onClick={() => onChange(filter.id)}
        >
          {filter.label}
          {loading && active === filter.id ? <LoadingSpinner className="filter-button-spinner" /> : null}
          <span>{counts[filter.id]}</span>
        </button>
      ))}
    </div>
  );
}
