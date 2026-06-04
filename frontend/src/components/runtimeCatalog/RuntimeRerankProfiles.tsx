import { formatInteger, formatNumber } from "../../libs/format";
import type { RuntimeCatalog } from "../../types";
import { SectionHeader } from "../SectionHeader";

export function RuntimeRerankProfiles({ profiles }: { profiles: RuntimeCatalog["rerankProfiles"] }) {
  return (
    <section className="runtime-panel">
      <SectionHeader title="Rerank profiles" description="Query intent profiles used to tune vector and reranker balance." />
      <div className="runtime-profile-grid">
        {profiles.map((profile) => (
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
        {profiles.length === 0 ? <div className="empty-state compact">No rerank profiles are registered.</div> : null}
      </div>
    </section>
  );
}
