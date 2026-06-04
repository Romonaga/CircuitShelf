import { useCallback, useMemo, useRef, useState } from "react";
import { getReviewDocuments } from "../../libs/api";
import { errorMessage } from "../../libs/errors";
import type { ReviewDocument } from "../../types";
import { filterReviewDocuments, selectNextReviewSource } from "../../libs/review/reviewQueue";

export function useReviewDocuments() {
  const [documents, setDocuments] = useState<ReviewDocument[]>([]);
  const [selected, setSelected] = useState("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selectedRef = useRef("");

  const filteredDocuments = useMemo(
    () => filterReviewDocuments(documents, filter),
    [documents, filter]
  );

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.source === selected) || null,
    [documents, selected]
  );

  const loadDocuments = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const response = await getReviewDocuments();
      setDocuments(response.documents);
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

  return {
    busy,
    documents,
    error,
    filter,
    filteredDocuments,
    loadDocuments,
    selected,
    selectedDocument,
    setError,
    setFilter,
    setSelected: selectDocument
  };
}
