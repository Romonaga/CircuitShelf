import type { RuntimeEquationPattern } from "../../types";
import { SectionHeader } from "../SectionHeader";

export function RuntimeEquationPatterns({
  groups,
  patternFilter,
  patterns,
  onPatternFilterChange
}: {
  groups: { type: string; patterns: RuntimeEquationPattern[] }[];
  patternFilter: string;
  patterns: RuntimeEquationPattern[];
  onPatternFilterChange: (value: string) => void;
}) {
  return (
    <section className="runtime-panel">
      <SectionHeader
        title="Equation patterns"
        description="Symbols and phrases used to preserve useful math during chunking."
        actions={
          <select value={patternFilter} onChange={(event) => onPatternFilterChange(event.target.value)} aria-label="Pattern group">
            <option value="all">All groups</option>
            {groups.map((group) => (
              <option key={group.type} value={group.type}>
                {group.type} ({group.patterns.length})
              </option>
            ))}
          </select>
        }
      />
      <div className="runtime-pattern-list">
        {patterns.map((pattern) => (
          <div className="runtime-pattern-row" key={pattern.id}>
            <span>{pattern.patternType}</span>
            <code>{pattern.pattern}</code>
            <em>{pattern.isRegex ? "regex" : "literal"}</em>
          </div>
        ))}
        {patterns.length === 0 ? <div className="empty-state compact">No equation patterns match this filter.</div> : null}
      </div>
    </section>
  );
}
