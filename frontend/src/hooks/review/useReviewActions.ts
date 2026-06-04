import { useState } from "react";
import {
  approveReviewDocument,
  reindexReviewDocument,
  removeReviewDocument,
  updateReviewDocumentScope
} from "../../libs/api";
import { errorMessage } from "../../libs/errors";
import { formatInteger } from "../../libs/format";
import type { ReviewDocument, ReviewScopeAudit } from "../../types";

export function useReviewActions({
  selectedDocument,
  clearDetails,
  loadDocuments,
  onStatusChange,
  onScopeAuditChange,
  setError
}: {
  selectedDocument: ReviewDocument | null;
  clearDetails: () => void;
  loadDocuments: () => Promise<void>;
  onStatusChange: () => void;
  onScopeAuditChange: (audit: ReviewScopeAudit[]) => void;
  setError: (message: string) => void;
}) {
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState("");

  async function runDocumentAction(errorPrefix: string, action: () => Promise<void>) {
    setActionBusy(true);
    setError("");
    setMessage("");
    try {
      await action();
      await loadDocuments();
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, errorPrefix));
    } finally {
      setActionBusy(false);
    }
  }

  async function approveSelected(includeImages: boolean) {
    if (!selectedDocument) {
      return;
    }
    await runDocumentAction("Could not approve document", async () => {
      await approveReviewDocument(selectedDocument.source, includeImages);
      setMessage(
        includeImages
          ? `${selectedDocument.displayName} approved for retrieval with images.`
          : `${selectedDocument.displayName} approved for retrieval without images.`
      );
      clearDetails();
    });
  }

  async function removeSelected() {
    if (!selectedDocument) {
      return;
    }
    await runDocumentAction("Could not remove document", async () => {
      await removeReviewDocument(selectedDocument.source);
      setMessage(`${selectedDocument.displayName} removed.`);
    });
  }

  async function reindexSelected() {
    if (!selectedDocument) {
      return;
    }
    await runDocumentAction("Could not re-index document", async () => {
      const result = await reindexReviewDocument(selectedDocument.source);
      setMessage(`${selectedDocument.displayName} queued for re-index${result.indexing?.jobId ? ` as job ${formatInteger(result.indexing.jobId)}` : ""}.`);
    });
  }

  async function changeSelectedScope(scope: "global" | "entity") {
    if (!selectedDocument) {
      return;
    }
    await runDocumentAction("Could not change document scope", async () => {
      const label = scope === "global" ? "global corpus" : "entity private";
      const result = await updateReviewDocumentScope(selectedDocument.source, scope, `Review screen changed scope to ${label}`);
      onScopeAuditChange(result.scopeAudit || []);
      setMessage(`${selectedDocument.displayName} changed to ${label}.`);
    });
  }

  return {
    actionBusy,
    approveSelected,
    changeSelectedScope,
    message,
    reindexSelected,
    removeSelected
  };
}
