import type { ReviewScopeAudit } from "../../types";
import { formatInteger } from "../../libs/format";

export function ReviewScopeAuditSection({ rows }: { rows: ReviewScopeAudit[] }) {
  if (!rows.length) {
    return null;
  }
  return (
    <details className="review-scope-audit">
      <summary>Scope history ({formatInteger(rows.length)})</summary>
      <div className="review-scope-audit-list">
        {rows.map((row) => (
          <article key={row.id} className="review-scope-audit-row">
            <strong>{scopeName(row.newIsGlobal, row.newEntityName)}</strong>
            <span>from {scopeName(Boolean(row.previousIsGlobal), row.previousEntityName)}</span>
            <span>{row.changedByUsername || "system"}</span>
            <span>{row.createdAt ? new Date(row.createdAt).toLocaleString() : "unknown time"}</span>
            {row.reason ? <small>{row.reason}</small> : null}
          </article>
        ))}
      </div>
    </details>
  );
}

function scopeName(isGlobal: boolean, entityName?: string) {
  return isGlobal ? "Global corpus" : `Entity: ${entityName || "Private"}`;
}
