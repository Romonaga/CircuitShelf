import { type MouseEvent, useState } from "react";
import { reindexReviewDocument, removeIndexedDocument, triggerIndexCheck } from "../libs/api";
import type { DocumentSummary, StatusPayload } from "../types";
import { errorMessage } from "../libs/errors";
import { formatInteger } from "../libs/format";
import { useDocumentBrowser } from "../hooks/useDocumentBrowser";
import { DocumentContextMenu, type DocumentContextMenuState, type DocumentMenuItem } from "./DocumentContextMenu";
import { DocumentUploadPanel } from "./DocumentUploadPanel";
import { DocumentDetailPanel } from "./documents/DocumentDetailPanel";
import { DocumentListPanel } from "./documents/DocumentListPanel";

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
  showEmptyInspector = true,
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
  showEmptyInspector?: boolean;
  scope?: "visible" | "global";
}) {
  const browser = useDocumentBrowser({ isActive, refreshSignal, scope });
  const [message, setMessage] = useState("");
  const [busyAction, setBusyAction] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [reindexing, setReindexing] = useState(false);
  const [contextMenu, setContextMenu] = useState<DocumentContextMenuState | null>(null);

  async function runIndexCheck() {
    setBusyAction(true);
    browser.setError("");
    setMessage("");
    try {
      const response = await triggerIndexCheck();
      setMessage(response.started ? "Incremental index check started." : "An index job is already running.");
      onStatusChange();
    } catch (err) {
      browser.setError(errorMessage(err, "Could not start index check"));
    } finally {
      setBusyAction(false);
    }
  }

  function openDocumentContextMenu(event: MouseEvent, document: DocumentSummary) {
    if (!isAdmin) {
      return;
    }
    event.preventDefault();
    browser.setSelected(document.source);
    setContextMenu({ document, x: event.clientX, y: event.clientY });
  }

  async function reindexDocument(document: DocumentMenuItem) {
    const displayName = document.displayName ?? document.source;
    setReindexing(true);
    browser.setError("");
    setMessage("");
    try {
      const result = await reindexReviewDocument(document.source);
      setMessage(`${displayName} queued for re-index${result.indexing?.jobId ? ` as job ${formatInteger(result.indexing.jobId)}` : ""}.`);
      onStatusChange();
    } catch (err) {
      browser.setError(errorMessage(err, "Could not re-index document"));
    } finally {
      setContextMenu(null);
      setReindexing(false);
    }
  }

  async function removeDocument(document: DocumentMenuItem) {
    const displayName = document.displayName ?? document.source;
    const confirmed = window.confirm(
      `Remove ${displayName} from CircuitShelf?\n\nThis removes its database rows and deletes the source file from the training folder so it is not re-indexed.`
    );
    if (!confirmed) {
      setContextMenu(null);
      return;
    }

    setRemoving(true);
    browser.setError("");
    setMessage("");
    try {
      const result = await removeIndexedDocument(document.source);
      setMessage(`${displayName} removed from CircuitShelf${result.deletedFile ? " and deleted from training." : "."}`);
      browser.clearDetail();
      await browser.loadDocuments();
      onStatusChange();
    } catch (err) {
      browser.setError(errorMessage(err, "Could not remove document"));
    } finally {
      setContextMenu(null);
      setRemoving(false);
    }
  }

  const listDescription = description ?? `${formatInteger(browser.documents.length)} indexed sources`;
  const uploadPanel = isAdmin ? (
    <DocumentUploadPanel
      scope={scope === "global" ? "global" : "entity"}
      help={uploadHelp}
      onUploaded={setMessage}
      onError={browser.setError}
      onStatusChange={onStatusChange}
    />
  ) : null;
  const listActions = isAdmin ? (
    <button className="ghost-button" onClick={runIndexCheck} disabled={browser.busy || busyAction}>
      Check now
    </button>
  ) : null;

  return (
    <section className="view-grid docs-grid">
      <DocumentListPanel
        title={title}
        description={listDescription}
        busy={browser.busy}
        detailBusy={browser.detailBusy}
        documents={browser.filteredDocuments}
        filter={browser.filter}
        selected={browser.selected}
        error={browser.error}
        message={message}
        actions={listActions}
        uploadPanel={uploadPanel}
        onFilterChange={browser.setFilter}
        onSelect={browser.setSelected}
        onContextMenu={openDocumentContextMenu}
      />
      <DocumentDetailPanel
        detail={browser.detail}
        detailBusy={browser.detailBusy}
        emptyText={emptyText}
        isAdmin={isAdmin}
        selectedDocument={browser.selectedDocument}
        selectedPage={browser.selectedPageDetail}
        showEmptyInspector={showEmptyInspector}
        scope={scope}
        status={status}
        onOpenReview={onOpenReview}
        onSelectPage={browser.setSelectedPage}
      />
      {isAdmin ? (
        <DocumentContextMenu
          menu={contextMenu}
          removing={removing}
          reindexing={reindexing}
          onClose={() => setContextMenu(null)}
          onReindex={(document) => void reindexDocument(document)}
          onRemove={(document) => void removeDocument(document)}
        />
      ) : null}
    </section>
  );
}
