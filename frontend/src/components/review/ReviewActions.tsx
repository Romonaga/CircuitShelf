import type { ReviewDocument } from "../../types";

export function ReviewActions({
  actionBusy,
  approveSelected,
  canManageSystem,
  changeSelectedScope,
  detailBusy,
  selectedDocument
}: {
  actionBusy: boolean;
  approveSelected: (includeImages: boolean) => void;
  canManageSystem: boolean;
  changeSelectedScope: (scope: "global" | "entity") => void;
  detailBusy: boolean;
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
    </div>
  );
}
