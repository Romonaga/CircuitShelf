import { useCallback, useEffect, useMemo, useState } from "react";
import { approveReviewDocument, getReviewDocument, getReviewDocuments, reindexReviewDocument, removeReviewDocument } from "../api";
import type { ReviewChunk, ReviewDocument } from "../types";
import { errorMessage } from "../lib/errors";
import { formatInteger } from "../lib/format";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function ReviewView({ onStatusChange }: { onStatusChange: () => void }) {
  const [documents, setDocuments] = useState<ReviewDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [chunks, setChunks] = useState<ReviewChunk[]>([]);
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const filteredDocuments = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return documents;
    }
    return documents.filter((doc) => `${doc.displayName} ${doc.source} ${doc.status}`.toLowerCase().includes(needle));
  }, [documents, filter]);

  const selectedDocument = documents.find((doc) => doc.source === selected) || null;

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getReviewDocuments();
      setDocuments(response.documents);
      const nextSelected = response.documents.find((doc) => doc.source === selected) || response.documents[0];
      setSelected(nextSelected?.source || "");
    } catch (err) {
      setError(errorMessage(err, "Could not load review queue"));
    } finally {
      setBusy(false);
    }
  }, [selected]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (!selected) {
      setChunks([]);
      return;
    }
    let active = true;
    getReviewDocument(selected)
      .then((response) => {
        if (active) {
          setChunks(response.chunks);
        }
      })
      .catch((err) => setError(errorMessage(err, "Could not load review details")));
    return () => {
      active = false;
    };
  }, [selected]);

  async function approveSelected() {
    if (!selectedDocument) {
      return;
    }
    setActionBusy(true);
    setError("");
    setMessage("");
    try {
      await approveReviewDocument(selectedDocument.source);
      setMessage(`${selectedDocument.displayName} approved for retrieval.`);
      await loadDocuments();
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Could not approve document"));
    } finally {
      setActionBusy(false);
    }
  }

  async function removeSelected() {
    if (!selectedDocument) {
      return;
    }
    setActionBusy(true);
    setError("");
    setMessage("");
    try {
      await removeReviewDocument(selectedDocument.source);
      setMessage(`${selectedDocument.displayName} removed.`);
      await loadDocuments();
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Could not remove document"));
    } finally {
      setActionBusy(false);
    }
  }

  async function reindexSelected() {
    if (!selectedDocument) {
      return;
    }
    setActionBusy(true);
    setError("");
    setMessage("");
    try {
      const result = await reindexReviewDocument(selectedDocument.source);
      setMessage(`${selectedDocument.displayName} re-indexed: ${formatInteger(result.chunks)} chunks, ${formatInteger(result.images)} images.`);
      await loadDocuments();
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Could not re-index document"));
    } finally {
      setActionBusy(false);
    }
  }

  return (
    <section className="view-grid docs-grid">
      <div className="document-list-panel">
        <SectionHeader title="Review" description={busy ? "Loading..." : `${formatInteger(documents.length)} pending documents`} />
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter review queue" />
        {message ? <p className="success-message">{message}</p> : null}
        <ErrorMessage message={error} />
        <div className="document-list">
          {filteredDocuments.map((document) => (
            <button
              key={document.source}
              className={document.source === selected ? "document-row active" : "document-row"}
              onClick={() => setSelected(document.source)}
            >
              <span>{document.displayName}</span>
              <small>
                {document.status} | {formatInteger(document.chunkCount)} chunks | {formatInteger(document.imageCount)} images
              </small>
            </button>
          ))}
          {!filteredDocuments.length ? <div className="empty-state compact">No documents need review.</div> : null}
        </div>
      </div>
      <div className="chunk-panel">
        <SectionHeader
          title={selectedDocument?.displayName || "No document selected"}
          description={
            selectedDocument
              ? `Quality ${selectedDocument.avgQuality.toFixed(2)} | ${formatInteger(selectedDocument.lowQualityCount)} low-quality chunks`
              : "Review new or changed documents before retrieval."
          }
          actions={
            selectedDocument ? (
              <div className="review-actions">
                <button className="primary-button" onClick={approveSelected} disabled={actionBusy}>
                  Approve
                </button>
                <button className="ghost-button" onClick={reindexSelected} disabled={actionBusy}>
                  Re-index
                </button>
                <button className="ghost-button danger-button" onClick={removeSelected} disabled={actionBusy}>
                  Remove
                </button>
              </div>
            ) : null
          }
        />
        <div className="chunk-table">
          {chunks.map((chunk) => (
            <article key={chunk.index} className={chunk.quality < 0.35 ? "chunk-row warning-row" : "chunk-row"}>
              <div className="chunk-meta">
                <strong>#{chunk.index}</strong>
                <span>{chunk.section}</span>
                <span>{chunk.category}</span>
                <span>{formatInteger(chunk.tokens)} tokens</span>
                <span>Quality {chunk.quality.toFixed(2)}</span>
                {chunk.page ? <span>Page {chunk.page}</span> : null}
                {chunk.isOcr ? <span>OCR</span> : null}
                {chunk.hasMath ? <span>Math</span> : null}
              </div>
              <p>{chunk.preview}</p>
              {chunk.qualityFlags.length ? <small>{chunk.qualityFlags.join(", ")}</small> : null}
            </article>
          ))}
          {!chunks.length ? <div className="empty-state">Select a document to inspect review chunks.</div> : null}
        </div>
      </div>
    </section>
  );
}
