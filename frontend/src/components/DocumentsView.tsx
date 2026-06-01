import { type MouseEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDocument, getDocuments, removeIndexedDocument, triggerIndexCheck } from "../api";
import type { DocumentDetail, DocumentSummary, StatusPayload } from "../types";
import { errorMessage } from "../lib/errors";
import { formatInteger } from "../lib/format";
import { ErrorMessage } from "./ErrorMessage";
import { DocumentContextMenu, type DocumentContextMenuState } from "./DocumentContextMenu";
import { IngestStatusPanel } from "./IngestStatusPanel";
import { DocumentPageInspector } from "./DocumentPageInspector";
import { DocumentStatsPanel } from "./DocumentStatsPanel";
import { DocumentUploadPanel } from "./DocumentUploadPanel";
import { LoadingSpinner } from "./LoadingSpinner";
import { SectionHeader } from "./SectionHeader";

export function DocumentsView({
  isActive,
  isAdmin,
  status,
  refreshSignal,
  onStatusChange,
  onOpenReview,
  title = "Documents",
  description,
  uploadHelp,
  emptyText = "Select a document to inspect its pages, chunks, images, and pinout.",
  scope = "visible"
}: {
  isActive: boolean;
  isAdmin: boolean;
  status: StatusPayload | null;
  refreshSignal: string;
  onStatusChange: () => void;
  onOpenReview: () => void;
  title?: string;
  description?: string;
  uploadHelp?: string;
  emptyText?: string;
  scope?: "visible" | "global";
}) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [selectedPage, setSelectedPage] = useState<number | string | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [contextMenu, setContextMenu] = useState<DocumentContextMenuState | null>(null);
  const selectedRef = useRef("");

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  const filteredDocuments = useMemo(() => {
    const needle = filter.toLowerCase();
    return documents.filter((document) =>
      `${document.displayName ?? document.source} ${document.source}`.toLowerCase().includes(needle)
    );
  }, [documents, filter]);

  const selectedPageDetail = useMemo(() => {
    if (!detail?.pages.length) {
      return null;
    }
    return detail.pages.find((page) => String(page.page) === String(selectedPage)) || detail.pages[0];
  }, [detail, selectedPage]);

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getDocuments(scope);
      setDocuments(response.documents);
      const nextSelected = response.documents.find((document) => document.source === selectedRef.current) || response.documents[0];
      setSelected(nextSelected?.source || "");
    } catch (err) {
      setError(errorMessage(err, "Could not load documents"));
    } finally {
      setBusy(false);
    }
  }, [scope]);

  useEffect(() => {
    if (isActive || refreshSignal) {
      void loadDocuments();
    }
  }, [isActive, loadDocuments, refreshSignal]);

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

  function openDocumentContextMenu(event: MouseEvent, document: DocumentSummary) {
    if (!isAdmin) {
      return;
    }
    event.preventDefault();
    setSelected(document.source);
    setContextMenu({ document, x: event.clientX, y: event.clientY });
  }

  async function removeDocument(document: DocumentSummary) {
    const displayName = document.displayName ?? document.source;
    const confirmed = window.confirm(
      `Remove ${displayName} from CircuitShelf?\n\nThis removes its database rows and deletes the source file from the training folder so it is not re-indexed.`
    );
    if (!confirmed) {
      setContextMenu(null);
      return;
    }

    setRemoving(true);
    setError("");
    setMessage("");
    try {
      const result = await removeIndexedDocument(document.source);
      setMessage(`${displayName} removed from CircuitShelf${result.deletedFile ? " and deleted from training." : "."}`);
      setDetail(null);
      setSelectedPage(null);
      await loadDocuments();
      onStatusChange();
    } catch (err) {
      setError(errorMessage(err, "Could not remove document"));
    } finally {
      setContextMenu(null);
      setRemoving(false);
    }
  }

  useEffect(() => {
    if (!selected) {
      setDetail(null);
      setSelectedPage(null);
      setDetailBusy(false);
      return;
    }
    let active = true;
    setDetailBusy(true);
    setDetail(null);
    setSelectedPage(null);
    setError("");
    getDocument(selected, scope)
      .then((response) => {
        if (active) {
          setDetail(response);
          setSelectedPage(response.pages[0]?.page ?? null);
        }
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load document"));
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
  }, [selected, scope]);

  return (
    <section className="view-grid docs-grid">
      <div className="document-list-panel">
        <SectionHeader
          title={title}
          description={busy ? "Loading..." : (description ?? `${formatInteger(documents.length)} indexed sources`)}
          actions={
            isAdmin ? (
              <button className="ghost-button" onClick={runIndexCheck} disabled={busy}>
                Check now
              </button>
            ) : null
          }
        />
        {isAdmin ? (
          <DocumentUploadPanel
            scope={scope === "global" ? "global" : "entity"}
            help={uploadHelp}
            onUploaded={setMessage}
            onError={setError}
            onStatusChange={onStatusChange}
          />
        ) : null}
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter documents" />
        {message ? <p className="success-message">{message}</p> : null}
        <ErrorMessage message={error} />
        <div className="document-list">
          {filteredDocuments.map((document) => (
            <button
              key={document.source}
              className={document.source === selected ? "document-row active" : "document-row"}
              onClick={() => setSelected(document.source)}
              onContextMenu={(event) => openDocumentContextMenu(event, document)}
            >
              <span className="document-row-title">
                {document.displayName ?? document.source}
                {detailBusy && document.source === selected ? <LoadingSpinner className="document-row-spinner" /> : null}
              </span>
              <small>
                {formatInteger(document.chunkCount)} chunks | {formatInteger(document.imageCount)} images
              </small>
            </button>
          ))}
        </div>
        {isAdmin ? (
          <DocumentContextMenu
            menu={contextMenu}
            removing={removing}
            onClose={() => setContextMenu(null)}
            onRemove={(document) => void removeDocument(document)}
          />
        ) : null}
      </div>
      <div className="chunk-panel">
        {isAdmin ? (
          <IngestStatusPanel
            ingest={status?.ingest}
            workerBudget={status?.ingestWorkerBudget}
            pendingReview={status?.pendingReview}
            onOpenReview={onOpenReview}
          />
        ) : null}
        <SectionHeader
          title={documents.find((document) => document.source === selected)?.displayName ?? selected ?? "No document selected"}
          description={detailBusy ? "Loading document details..." : `${formatInteger(detail?.chunks.length ?? 0)} chunks | ${formatInteger(detail?.images.length ?? 0)} images`}
        />
        {detailBusy ? (
          <div className="document-loading">
            <LoadingSpinner />
            <span>Loading document details...</span>
          </div>
        ) : null}
        {!detailBusy ? <DocumentStatsPanel detail={detail} /> : null}
        {!detailBusy && detail?.pages.length ? (
          <div className="document-explorer">
            <div className="page-strip">
              {detail.pages.map((page) => (
                <button
                  key={page.page}
                  className={String(page.page) === String(selectedPageDetail?.page) ? "page-chip active" : "page-chip"}
                  onClick={() => setSelectedPage(page.page)}
                >
                  Page {page.page}
                  <small>{formatInteger(page.chunks.length)} chunks | {formatInteger(page.images.length)} images</small>
                </button>
              ))}
            </div>
            <div className="page-detail">
              {selectedPageDetail ? <DocumentPageInspector page={selectedPageDetail} /> : null}
            </div>
          </div>
        ) : !detailBusy ? (
          <div className="empty-state">{emptyText}</div>
        ) : null}
      </div>
    </section>
  );
}
