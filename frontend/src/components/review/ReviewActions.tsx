import { useState } from "react";

import type { ReviewDocument } from "../../types";

const DEFAULT_MIN_QUALITY = 0.35;

export function ReviewActions({
  actionBusy,
  approveSelected,
  canManageSystem,
  changeSelectedScope,
  detailBusy,
  downloadSelected,
  reindexSelected,
  removeSelected,
  selectedCount,
  selectedDocument
}: {
  actionBusy: boolean;
  approveSelected: (includeImages: boolean, minQuality?: number) => void;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  detailBusy: boolean;
  downloadSelected: () => void;
  reindexSelected: () => void;
  removeSelected: () => void;
  selectedCount: number;
  selectedDocument: ReviewDocument;
}) {
  const [minQuality, setMinQuality] = useState(DEFAULT_MIN_QUALITY);
  const disabled = actionBusy || detailBusy;
  const targetLabel = selectedCount > 0 ? ` ${selectedCount}` : "";
  const hasImages = selectedCount > 0 || selectedDocument.imageCount > 0;
  const normalizedMinQuality = Math.max(0, Math.min(1, Number.isFinite(minQuality) ? minQuality : DEFAULT_MIN_QUALITY));
  return (
    <div className="review-actions">
      <label className="review-quality-threshold">
        <span>Keep quality &gt;=</span>
        <input
          type="number"
          min="0"
          max="1"
          step="0.05"
          value={normalizedMinQuality.toFixed(2)}
          disabled={disabled}
          onChange={(event) => setMinQuality(Number(event.target.value))}
        />
      </label>
      <button className="primary-button" onClick={() => approveSelected(true, normalizedMinQuality)} disabled={disabled}>
        Approve{targetLabel} with images
      </button>
      {hasImages ? (
        <button className="ghost-button" onClick={() => approveSelected(false, normalizedMinQuality)} disabled={disabled}>
          Approve{targetLabel} text only
        </button>
      ) : null}
      {canManageSystem && !selectedDocument.isGlobal ? (
        <button className="ghost-button" onClick={() => changeSelectedScope("global")} disabled={disabled}>
          Promote to corpus
        </button>
      ) : null}
      {canManageSystem && selectedDocument.isGlobal ? (
        <button className="ghost-button" onClick={() => changeSelectedScope("entity")} disabled={disabled}>
          Make entity-private
        </button>
      ) : null}
      <button className="ghost-button" onClick={downloadSelected} disabled={disabled}>
        Download
      </button>
      <button className="ghost-button" onClick={reindexSelected} disabled={disabled}>
        Re-index{targetLabel}
      </button>
      <button className="danger-button" onClick={removeSelected} disabled={disabled}>
        Delete{targetLabel}
      </button>
    </div>
  );
}
