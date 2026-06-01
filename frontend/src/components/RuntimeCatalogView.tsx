import { useMemo, useState } from "react";
import { formatInteger, formatNumber } from "../lib/format";
import { useRuntimeCatalog } from "../hooks/useRuntimeCatalog";
import type { RuntimeEquationPattern } from "../types";
import { ErrorMessage } from "./ErrorMessage";
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

      <section className="runtime-panel">
        <SectionHeader title="LLM models" description="Local model options and default generation settings." />
        <div className="runtime-table runtime-model-table">
          <div className="runtime-table-head">
            <span>Model</span>
            <span>Provider</span>
            <span>Status</span>
            <span>Temp</span>
            <span>Predict</span>
            <span>Context</span>
          </div>
          {(catalog?.llmModels ?? []).map((model) => (
            <div className="runtime-table-row" key={model.id}>
              <strong>{model.displayName || model.modelName}</strong>
              <span>{model.provider}</span>
              <span>{model.isDefault ? "Default" : model.isEnabled ? "Enabled" : "Disabled"}</span>
              <span>{formatNumber(model.temperature)}</span>
              <span>{formatInteger(model.numPredict)}</span>
              <span>{model.numCtx ? formatInteger(model.numCtx) : "default"}</span>
            </div>
          ))}
          {catalog?.llmModels.length === 0 ? <div className="empty-state compact">No LLM models are registered.</div> : null}
        </div>
      </section>

      <section className="runtime-panel">
        <SectionHeader title="Rerank profiles" description="Query intent profiles used to tune vector and reranker balance." />
        <div className="runtime-profile-grid">
          {(catalog?.rerankProfiles ?? []).map((profile) => (
            <article className="runtime-profile-card" key={profile.id}>
              <div>
                <h3>{profile.name}</h3>
                {profile.isDefault ? <span>Default</span> : null}
              </div>
              <dl>
                <div>
                  <dt>Vector</dt>
                  <dd>{formatNumber(profile.weightVector)}</dd>
                </div>
                <div>
                  <dt>Rerank</dt>
                  <dd>{formatNumber(profile.weightRerank)}</dd>
                </div>
                <div>
                  <dt>Keywords</dt>
                  <dd>{formatInteger(profile.keywords.length)}</dd>
                </div>
              </dl>
              <div className="runtime-keywords">
                {profile.keywords.slice(0, 18).map((keyword) => (
                  <span key={keyword}>{keyword}</span>
                ))}
                {profile.keywords.length > 18 ? <em>+{profile.keywords.length - 18}</em> : null}
              </div>
            </article>
          ))}
          {catalog?.rerankProfiles.length === 0 ? <div className="empty-state compact">No rerank profiles are registered.</div> : null}
        </div>
      </section>

      <section className="runtime-panel">
        <SectionHeader
          title="Equation patterns"
          description="Symbols and phrases used to preserve useful math during chunking."
          actions={
            <select value={patternFilter} onChange={(event) => setPatternFilter(event.target.value)} aria-label="Pattern group">
              <option value="all">All groups</option>
              {patternGroups.map((group) => (
                <option key={group.type} value={group.type}>
                  {group.type} ({group.patterns.length})
                </option>
              ))}
            </select>
          }
        />
        <div className="runtime-pattern-list">
          {visiblePatterns.map((pattern) => (
            <div className="runtime-pattern-row" key={pattern.id}>
              <span>{pattern.patternType}</span>
              <code>{pattern.pattern}</code>
              <em>{pattern.isRegex ? "regex" : "literal"}</em>
            </div>
          ))}
          {visiblePatterns.length === 0 ? <div className="empty-state compact">No equation patterns match this filter.</div> : null}
        </div>
      </section>
    </section>
  );
}
