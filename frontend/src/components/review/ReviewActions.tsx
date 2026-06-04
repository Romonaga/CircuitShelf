import type { ReviewDocument } from "../../types";

export function ReviewActions({
  actionBusy,
  approveSelected,
  canManageSystem,
  changeSelectedScope,
  detailBusy,
  reindexSelected,
  removeSelected,
  selectedDocument
}: {
  actionBusy: boolean;
  approveSelected: (includeImages: boolean) => void;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  detailBusy: boolean;
  reindexSelected: () => void;
  removeSelected: () => void;
  selectedDocument: ReviewDocument;
}) {
  const disabled = actionBusy || detailBusy;
  return (
    <div className="review-actions">
      <button className="primary-button" onClick={() => approveSelected(true)} disabled={disabled}>
        Approve with images
      </button>
      {selectedDocument.imageCount > 0 ? (
        <button className="ghost-button" onClick={() => approveSelected(false)} disabled={disabled}>
          Approve text only
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
      <button className="ghost-button" onClick={reindexSelected} disabled={disabled}>
        Re-index
      </button>
      <button className="ghost-button danger-button" onClick={removeSelected} disabled={disabled}>
        Remove
      </button>
    </div>
  );
}
