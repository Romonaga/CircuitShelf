import { useMemo, useState } from "react";
import { formatInteger } from "../libs/format";
import { useRuntimeCatalog } from "../hooks/useRuntimeCatalog";
import type { RuntimeEquationPattern } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { RuntimeEquationPatterns } from "./runtimeCatalog/RuntimeEquationPatterns";
import { RuntimeModelTable } from "./runtimeCatalog/RuntimeModelTable";
import { RuntimeRerankProfiles } from "./runtimeCatalog/RuntimeRerankProfiles";
import { SectionHeader } from "./SectionHeader";
import { Stat } from "./Stat";

export function RuntimeCatalogView({ isActive }: { isActive: boolean }) {
  const { catalog, loading, error, refresh } = useRuntimeCatalog(isActive);
  const [patternFilter, setPatternFilter] = useState("all");

  const patternGroups = useMemo(() => {
    const groups = new Map<string, RuntimeEquationPattern[]>();
    (catalog?.equationPatterns ?? []).forEach((pattern) => {
      const group = pattern.patternType || "unknown";
      groups.set(group, [...(groups.get(group) ?? []), pattern]);
    });
    return Array.from(groups, ([type, patterns]) => ({ type, patterns }));
  }, [catalog?.equationPatterns]);

  const visiblePatterns = useMemo(() => {
    if (!catalog) {
      return [];
    }
    if (patternFilter === "all") {
      return catalog.equationPatterns;
    }
    return catalog.equationPatterns.filter((pattern) => pattern.patternType === patternFilter);
  }, [catalog, patternFilter]);

  return (
    <section className="runtime-catalog-page">
      <SectionHeader
        title="Runtime catalog"
        description={loading ? "Loading DB-backed runtime records..." : "Models, reranking profiles, and math detection rules loaded from Postgres."}
        actions={
          <button className="ghost-button" onClick={() => void refresh()} disabled={loading}>
            {loading ? "Refreshing..." : "Refresh"}
          </button>
        }
      />
      <ErrorMessage message={error} />
      <div className="status-grid performance-stats">
        <Stat label="LLM models" value={formatInteger(catalog?.llmModels.length)} />
        <Stat label="Rerank profiles" value={formatInteger(catalog?.rerankProfiles.length)} />
        <Stat label="Rerank keywords" value={formatInteger((catalog?.rerankProfiles ?? []).reduce((total, profile) => total + profile.keywords.length, 0))} />
        <Stat label="Equation patterns" value={formatInteger(catalog?.equationPatterns.length)} />
        <Stat label="Pattern groups" value={formatInteger(patternGroups.length)} />
        <Stat label="Enabled models" value={formatInteger((catalog?.llmModels ?? []).filter((model) => model.isEnabled).length)} />
      </div>

      <RuntimeModelTable models={catalog?.llmModels ?? []} />
      <RuntimeRerankProfiles profiles={catalog?.rerankProfiles ?? []} />
      <RuntimeEquationPatterns
        groups={patternGroups}
        patternFilter={patternFilter}
        patterns={visiblePatterns}
        onPatternFilterChange={setPatternFilter}
      />
    </section>
  );
}
