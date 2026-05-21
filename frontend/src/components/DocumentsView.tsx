import { useCallback, useEffect, useMemo, useState } from "react";
import { getDocument, getDocuments } from "../api";
import type { DocumentChunk, DocumentSummary } from "../types";
import { errorMessage } from "../lib/errors";
import { formatInteger } from "../lib/format";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function DocumentsView() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

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
        <SectionHeader title="Documents" description={busy ? "Loading..." : `${formatInteger(documents.length)} indexed sources`} />
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter documents" />
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
