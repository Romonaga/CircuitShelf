import { useCallback, useEffect, useMemo, useState } from "react";
import { getDocument, getDocuments, triggerIndexCheck, uploadDocument } from "../api";
import type { DocumentChunk, DocumentSummary, StatusPayload } from "../types";
import { errorMessage } from "../lib/errors";
import { formatInteger } from "../lib/format";
import { ErrorMessage } from "./ErrorMessage";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { SectionHeader } from "./SectionHeader";

export function DocumentsView({
  isAdmin,
  status,
  onStatusChange,
  onOpenReview
}: {
  isAdmin: boolean;
  status: StatusPayload | null;
  onStatusChange: () => void;
  onOpenReview: () => void;
}) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [overwrite, setOverwrite] = useState(false);

  const filteredDocuments = useMemo(() => {
    const needle = filter.toLowerCase();
    return documents.filter((document) =>
      `${document.displayName ?? document.source} ${document.source}`.toLowerCase().includes(needle)
    );
  }, [documents, filter]);

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getDocuments();
      setDocuments(response.documents);
      if (!selected && response.documents.length) {
        setSelected(response.documents[0].source);
      }
    } catch (err) {
      setError(errorMessage(err, "Could not load documents"));
    } finally {
      setBusy(false);
    }
  }, [selected]);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  async function submitUpload() {
    if (!uploadFile) {
      return;
    }
    setUploading(true);
    setError("");
    setMessage("");
    try {
      const response = await uploadDocument(uploadFile, overwrite);
      setMessage(`${response.filename} uploaded. Incremental indexing ${response.indexing.started ? "started" : "is already running"}; it will appear in Review before retrieval.`);
      setUploadFile(null);
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  }

  async function runIndexCheck() {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const response = await triggerIndexCheck();
      setMessage(response.started ? "Incremental index check started." : "An index job is already running.");
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Could not start index check"));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!selected) {
      setChunks([]);
      return;
    }
    let active = true;
    getDocument(selected)
      .then((response) => {
        if (active) {
          setChunks(response.chunks);
        }
      })
      .catch((err) => setError(errorMessage(err, "Could not load document")));
    return () => {
      active = false;
    };
  }, [selected]);

  return (
    <section className="view-grid docs-grid">
      <div className="document-list-panel">
        <SectionHeader
          title="Documents"
          description={busy ? "Loading..." : `${formatInteger(documents.length)} indexed sources`}
          actions={
            isAdmin ? (
              <button className="ghost-button" onClick={runIndexCheck} disabled={busy || uploading}>
                Check now
              </button>
            ) : null
          }
        />
        {isAdmin ? (
          <div className="upload-panel">
            <input
              type="file"
              onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              disabled={uploading}
            />
            <label className="checkbox-label">
              <input type="checkbox" checked={overwrite} onChange={(event) => setOverwrite(event.target.checked)} />
              Replace existing
            </label>
            <button className="primary-button" onClick={submitUpload} disabled={!uploadFile || uploading}>
              {uploading ? "Uploading..." : "Upload"}
            </button>
          </div>
        ) : null}
        {isAdmin ? <IngestStatusPanel ingest={status?.ingest} pendingReview={status?.pendingReview} onOpenReview={onOpenReview} /> : null}
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter documents" />
        {message ? <p className="success-message">{message}</p> : null}
        <ErrorMessage message={error} />
        <div className="document-list">
          {filteredDocuments.map((document) => (
            <button
              key={document.source}
              className={document.source === selected ? "document-row active" : "document-row"}
              onClick={() => setSelected(document.source)}
            >
              <span>{document.displayName ?? document.source}</span>
              <small>
                {formatInteger(document.chunkCount)} chunks | {formatInteger(document.imageCount)} images
              </small>
            </button>
          ))}
        </div>
      </div>
      <div className="chunk-panel">
        <SectionHeader
          title={documents.find((document) => document.source === selected)?.displayName ?? selected ?? "No document selected"}
          description={`${formatInteger(chunks.length)} chunks`}
        />
        <div className="chunk-table">
          {chunks.map((chunk) => (
            <article key={chunk.index} className="chunk-row">
              <div className="chunk-meta">
                <strong>#{chunk.index}</strong>
                <span>{chunk.section}</span>
                <span>{chunk.category}</span>
                <span>{formatInteger(chunk.tokens)} tokens</span>
                {chunk.page ? <span>Page {chunk.page}</span> : null}
                {chunk.sourceImageId ? <span>{chunk.sourceImageId}</span> : null}
              </div>
              <p>{chunk.preview}</p>
            </article>
          ))}
          {!chunks.length ? <div className="empty-state">Select a document to inspect its chunks.</div> : null}
        </div>
      </div>
    </section>
  );
}
