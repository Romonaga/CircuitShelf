import { useState } from "react";
import {
  approveReviewDocument,
  batchReviewDocuments,
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
  selectedDocuments,
  clearDetails,
  clearSelection,
  loadDocuments,
  onStatusChange,
  onScopeAuditChange,
  setError
}: {
  selectedDocument: ReviewDocument | null;
  selectedDocuments: ReviewDocument[];
  clearDetails: () => void;
  clearSelection: () => void;
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

  function prunedSummary(prunedChunks: number): string {
    return prunedChunks > 0 ? `; ${formatInteger(prunedChunks)} chunks pruned below threshold` : "";
  }

  async function approveSelected(includeImages: boolean, minQuality?: number) {
    if (selectedDocuments.length > 0) {
      await runDocumentAction("Could not approve selected documents", async () => {
        const result = await batchReviewDocuments({
          sources: selectedDocuments.map((document) => document.source),
          action: "approve",
          includeImages,
          minQuality
        });
        const prunedChunks = result.results.reduce((total, item) => total + Number(item.prunedChunks || 0), 0);
        setMessage(
          includeImages
            ? `${formatInteger(result.okCount)} documents approved for retrieval with images${prunedSummary(prunedChunks)}${result.failedCount ? `; ${formatInteger(result.failedCount)} failed` : ""}.`
            : `${formatInteger(result.okCount)} documents approved for retrieval without images${prunedSummary(prunedChunks)}${result.failedCount ? `; ${formatInteger(result.failedCount)} failed` : ""}.`
        );
        clearDetails();
        clearSelection();
      });
      return;
    }
    if (!selectedDocument) {
      return;
    }
    await runDocumentAction("Could not approve document", async () => {
      const result = await approveReviewDocument(selectedDocument.source, includeImages, minQuality);
      setMessage(
        includeImages
          ? `${selectedDocument.displayName} approved for retrieval with images${prunedSummary(Number(result.prunedChunks || 0))}.`
          : `${selectedDocument.displayName} approved for retrieval without images${prunedSummary(Number(result.prunedChunks || 0))}.`
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

  async function reindexSelectedDocuments() {
    if (selectedDocuments.length === 0) {
      await reindexDocument(selectedDocument);
      return;
    }
    await runDocumentAction("Could not re-index selected documents", async () => {
      const result = await batchReviewDocuments({
        sources: selectedDocuments.map((document) => document.source),
        action: "reindex"
      });
      setMessage(`${formatInteger(result.okCount)} documents queued for re-index${result.failedCount ? `; ${formatInteger(result.failedCount)} failed` : ""}.`);
      clearSelection();
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
    if (selectedDocuments.length > 0) {
      await runDocumentAction("Could not change selected document scopes", async () => {
        const label = scope === "global" ? "global corpus" : "entity private";
        const result = await batchReviewDocuments({
          sources: selectedDocuments.map((document) => document.source),
          action: "scope",
          scope
        });
        setMessage(`${formatInteger(result.okCount)} documents changed to ${label}${result.failedCount ? `; ${formatInteger(result.failedCount)} failed` : ""}.`);
        clearSelection();
      });
      return;
    }
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
    reindexSelectedDocuments,
    message,
    removeDocument,
    async removeSelectedDocuments() {
      if (selectedDocuments.length === 0) {
        await removeDocument(selectedDocument);
        return;
      }
      await runDocumentAction("Could not remove selected documents", async () => {
        const result = await batchReviewDocuments({
          sources: selectedDocuments.map((document) => document.source),
          action: "remove",
          deleteFile: true
        });
        setMessage(`${formatInteger(result.okCount)} documents removed${result.failedCount ? `; ${formatInteger(result.failedCount)} failed` : ""}.`);
        clearDetails();
        clearSelection();
      });
    },
  };
}
