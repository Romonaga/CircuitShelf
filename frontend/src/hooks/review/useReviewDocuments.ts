import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getReviewDocuments } from "../../libs/api";
import { errorMessage } from "../../libs/errors";
import type { ReviewDocument } from "../../types";
import {
  defaultReviewTriageFilters,
  filterReviewDocuments,
  reviewFolderOptions,
  selectNextReviewSource,
  type ReviewDocumentKindFilter,
  type ReviewHealthFilter
} from "../../libs/review/reviewQueue";

export function useReviewDocuments() {
  const [documents, setDocuments] = useState<ReviewDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const [filters, setFilters] = useState(defaultReviewTriageFilters);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedRef = useRef("");

  const filteredDocuments = useMemo(
    () => filterReviewDocuments(documents, filters),
    [documents, filters]
  );

  const folderOptions = useMemo(
    () => reviewFolderOptions(documents),
    [documents]
  );

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.source === selected) || null,
    [documents, selected]
  );

  const selectedDocuments = useMemo(
    () => documents.filter((doc) => selectedSources.has(doc.source)),
    [documents, selectedSources]
  );

  const allFilteredSelected = useMemo(
    () => filteredDocuments.length > 0 && filteredDocuments.every((doc) => selectedSources.has(doc.source)),
    [filteredDocuments, selectedSources]
  );

  useEffect(() => {
    if (!filteredDocuments.length || filteredDocuments.some((doc) => doc.source === selected)) {
      return;
    }
    const nextSelected = filteredDocuments[0].source;
    selectedRef.current = nextSelected;
    setSelected(nextSelected);
  }, [filteredDocuments, selected]);

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getReviewDocuments();
      setDocuments(response.documents);
      const available = new Set(response.documents.map((doc) => doc.source));
      setSelectedSources((current) => new Set([...current].filter((source) => available.has(source))));
      setSelected(selectNextReviewSource(response.documents, selectedRef.current));
    } catch (err) {
      setError(errorMessage(err, "Could not load review queue"));
    } finally {
      setBusy(false);
    }
  }, []);

  const selectDocument = useCallback((source: string) => {
    selectedRef.current = source;
    setSelected(source);
  }, []);

  const toggleSelection = useCallback((source: string) => {
    setSelectedSources((current) => {
      const next = new Set(current);
      if (next.has(source)) {
        next.delete(source);
      } else {
        next.add(source);
      }
      return next;
    });
  }, []);

  const selectAllFiltered = useCallback(() => {
    setSelectedSources((current) => {
      const next = new Set(current);
      for (const document of filteredDocuments) {
        next.add(document.source);
      }
      return next;
    });
  }, [filteredDocuments]);

  const clearSelection = useCallback(() => {
    setSelectedSources(new Set());
  }, []);

  const setSearchFilter = useCallback((search: string) => {
    setFilters((current) => ({ ...current, search }));
  }, []);

  const setKindFilter = useCallback((kind: ReviewDocumentKindFilter) => {
    setFilters((current) => ({ ...current, kind }));
  }, []);

  const setHealthFilter = useCallback((health: ReviewHealthFilter) => {
    setFilters((current) => ({ ...current, health }));
  }, []);

  const setFolderFilter = useCallback((folder: string) => {
    setFilters((current) => ({ ...current, folder }));
  }, []);

  const resetFilters = useCallback(() => {
    setFilters(defaultReviewTriageFilters);
  }, []);

  return {
    allFilteredSelected,
    busy,
    clearSelection,
    documents,
    error,
    filters,
    filteredDocuments,
    folderOptions,
    loadDocuments,
    resetFilters,
    selected,
    selectedDocument,
    selectedDocuments,
    selectedSources: [...selectedSources],
    setError,
    setFolderFilter,
    setHealthFilter,
    setKindFilter,
    setSearchFilter,
    setSelected: selectDocument,
    selectAllFiltered,
    toggleSelection
  };
}
