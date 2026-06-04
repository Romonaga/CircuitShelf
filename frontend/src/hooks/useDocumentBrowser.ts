import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDocument, getDocuments } from "../libs/api";
import type { DocumentDetail, DocumentSummary } from "../types";
import { errorMessage } from "../libs/errors";

export type DocumentScope = "visible" | "global";

export function useDocumentBrowser({
  isActive,
  refreshSignal,
  scope
}: {
  isActive: boolean;
  refreshSignal: string;
  scope: DocumentScope;
}) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [selectedPage, setSelectedPage] = useState<number | string | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState(false);
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

  const selectedDocument = useMemo(
    () => documents.find((document) => document.source === selected) ?? null,
    [documents, selected]
  );

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

  function clearDetail() {
    setDetail(null);
    setSelectedPage(null);
  }

  return {
    busy,
    clearDetail,
    detail,
    detailBusy,
    documents,
    error,
    filter,
    filteredDocuments,
    loadDocuments,
    selected,
    selectedDocument,
    selectedPageDetail,
    setError,
    setFilter,
    setSelected,
    setSelectedPage
  };
}
