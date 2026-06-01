import type { ReviewDocument } from "../types";

export function ReviewScopeBadge({ document }: { document: Pick<ReviewDocument, "isGlobal" | "scopeLabel"> }) {
  const isGlobal = Boolean(document.isGlobal);
  return (
    <span className={isGlobal ? "scope-badge global" : "scope-badge private"}>
      {document.scopeLabel || (isGlobal ? "Global corpus" : "Entity private")}
    </span>
  );
}
