import type { ReviewDocument } from "../../types";

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
  approveSelected: (includeImages: boolean) => void;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  detailBusy: boolean;
  downloadSelected: () => void;
  reindexSelected: () => void;
  removeSelected: () => void;
  selectedCount: number;
  selectedDocument: ReviewDocument;
}) {
  const disabled = actionBusy || detailBusy;
  const targetLabel = selectedCount > 0 ? ` ${selectedCount}` : "";
  const hasImages = selectedCount > 0 || selectedDocument.imageCount > 0;
  return (
    <div className="review-actions">
      <button className="primary-button" onClick={() => approveSelected(true)} disabled={disabled}>
        Approve{targetLabel} with images
      </button>
      {hasImages ? (
        <button className="ghost-button" onClick={() => approveSelected(false)} disabled={disabled}>
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
