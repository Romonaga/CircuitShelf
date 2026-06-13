import type { ProjectCandidateFilter } from "../types";

const filters: Array<{ id: ProjectCandidateFilter; label: string }> = [
  { id: "all", label: "All" },
  { id: "buildable", label: "Buildable" },
  { id: "needs-parts", label: "Needs parts" }
];

export function ProjectCandidateFilters({
  active,
  counts,
  onChange
}: {
  active: ProjectCandidateFilter;
  counts: Record<ProjectCandidateFilter, number>;
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
          <span>{counts[filter.id]}</span>
        </button>
      ))}
    </div>
  );
}
