import type { ResponseValidation } from "../types";
import { formatNumber } from "../lib/format";

export function ResponseValidationPanel({ validation }: { validation?: ResponseValidation | null }) {
  if (!validation?.enabled) {
    return null;
  }

  const status = validation.ran ? (validation.useful ? "Validated" : "Needs review") : "Not validated";
  const detail = validation.ran
    ? `${validation.changed ? "Cleaned up" : "Checked"} in ${formatNumber((validation.elapsedMs || 0) / 1000)}s`
    : "Validator skipped by settings.";

  return (
    <aside className={`validation-panel ${validation.useful ? "ok" : "warn"}`}>
      <div>
        <strong>{status}</strong>
        <span>{detail}</span>
      </div>
      {validation.issues.length ? (
        <ul>
          {validation.issues.slice(0, 4).map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
    </aside>
  );
}
