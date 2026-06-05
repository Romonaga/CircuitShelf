import { useState } from "react";
import {
  approveReviewDocument,
  downloadReviewDocumentSource,
  reindexReviewDocument,
  removeReviewDocument,
  updateReviewDocumentScope
} from "../../libs/api";
import { downloadBlob } from "../../libs/download";
import { errorMessage } from "../../libs/errors";
import { formatInteger } from "../../libs/format";
import type { ReviewDocument, ReviewScopeAudit } from "../../types";

type ReviewActionDocument = Pick<ReviewDocument, "source"> & { displayName?: string };

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

  async function removeDocument(document: ReviewActionDocument | null) {
    if (!document) {
      return;
    }
    await runDocumentAction("Could not remove document", async () => {
      await removeReviewDocument(document.source);
      setMessage(`${document.displayName ?? document.source} removed.`);
    });
  }

  async function reindexDocument(document: ReviewActionDocument | null) {
    if (!document) {
      return;
    }
    await runDocumentAction("Could not re-index document", async () => {
      const result = await reindexReviewDocument(document.source);
      setMessage(`${document.displayName ?? document.source} queued for re-index${result.indexing?.jobId ? ` as job ${formatInteger(result.indexing.jobId)}` : ""}.`);
    });
  }

  async function downloadDocument(document: ReviewActionDocument | null) {
    if (!document) {
      return;
    }
    setActionBusy(true);
    setError("");
    setMessage("");
    try {
      const blob = await downloadReviewDocumentSource(document.source);
      downloadBlob(blob, document.displayName ?? document.source);
      setMessage(`${document.displayName ?? document.source} downloaded.`);
    } catch (err) {
      setError(errorMessage(err, "Could not download document"));
    } finally {
      setActionBusy(false);
    }
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
    downloadDocument,
    reindexDocument,
    message,
    removeDocument,
  };
}
