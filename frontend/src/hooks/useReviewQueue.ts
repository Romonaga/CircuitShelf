import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  approveReviewDocument,
  getReviewDocument,
  getReviewDocumentImages,
  getReviewDocuments,
  reindexReviewDocument,
  removeReviewDocument,
  updateReviewDocumentScope
} from "../api";
import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage, ReviewScopeAudit } from "../types";
import { errorMessage } from "../libs/errors";
import { formatInteger } from "../libs/format";

export const initialChunkPreviewLimit = 50;
export const maxChunkPreviewLimit = 500;

export function useReviewQueue({
  isActive,
  refreshSignal,
  onStatusChange
}: {
  isActive: boolean;
  refreshSignal: number;
  onStatusChange: () => void;
}) {
  const [documents, setDocuments] = useState<ReviewDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [chunks, setChunks] = useState<ReviewChunk[]>([]);
  const [chunkLimit, setChunkLimit] = useState(initialChunkPreviewLimit);
  const [images, setImages] = useState<ReviewImage[]>([]);
  const [intelligence, setIntelligence] = useState<DatasheetIntelligence | null>(null);
  const [scopeAudit, setScopeAudit] = useState<ReviewScopeAudit[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const selectedRef = useRef("");

  const filteredDocuments = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return documents;
    }
    return documents.filter((doc) => `${doc.displayName} ${doc.source} ${doc.status} ${doc.scopeLabel ?? ""}`.toLowerCase().includes(needle));
  }, [documents, filter]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.source === selected) || null,
    [documents, selected]
  );
  const totalChunkCount = selectedDocument?.chunkCount ?? chunks.length;
  const chunkPreviewCap = Math.min(totalChunkCount || maxChunkPreviewLimit, maxChunkPreviewLimit);
  const canLoadMoreChunks = Boolean(selectedDocument && chunks.length < totalChunkCount && chunkLimit < chunkPreviewCap);

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getReviewDocuments();
      setDocuments(response.documents);
      const nextSelected = response.documents.find((doc) => doc.source === selectedRef.current) || response.documents[0];
      setSelected(nextSelected?.source || "");
    } catch (err) {
      setError(errorMessage(err, "Could not load review queue"));
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      void loadDocuments();
    }
  }, [isActive, loadDocuments, refreshSignal]);

  useEffect(() => {
    if (!selected) {
      setChunks([]);
      setImages([]);
      setIntelligence(null);
      setScopeAudit([]);
      setDetailBusy(false);
      return;
    }
    let active = true;
    setDetailBusy(true);
    setChunks([]);
    setImages([]);
    setIntelligence(null);
    setScopeAudit([]);
    setError("");
    Promise.all([getReviewDocument(selected, chunkLimit), getReviewDocumentImages(selected)])
      .then(([documentResponse, imageResponse]) => {
        if (active) {
          setChunks(documentResponse.chunks);
          setIntelligence(documentResponse.intelligence ?? null);
          setScopeAudit(documentResponse.scopeAudit || []);
          setImages(imageResponse.images);
        }
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load review details"));
        }
      })
      .finally(() => {
        if (active) {
          setDetailBusy(false);
        }
      });
    return () => {
      active = false;
    };
  }, [selected, chunkLimit]);

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
      setChunks([]);
      setImages([]);
      setIntelligence(null);
      setScopeAudit([]);
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
      setScopeAudit(result.scopeAudit || []);
      setMessage(`${selectedDocument.displayName} changed to ${label}.`);
    });
  }

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

  return {
    actionBusy,
    approveSelected,
    busy,
    canLoadMoreChunks,
    changeSelectedScope,
    chunkLimit,
    chunkPreviewCap,
    chunks,
    detailBusy,
    documents,
    error,
    filter,
    filteredDocuments,
    images,
    intelligence,
    loadDocuments,
    message,
    reindexSelected,
    removeSelected,
    scopeAudit,
    selected,
    selectedDocument,
    setChunkLimit,
    setFilter,
    setSelected,
    totalChunkCount
  };
}
