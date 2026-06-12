import { useEffect, useState } from "react";
import { getReviewDocument, getReviewDocumentImages } from "../../libs/api";
import { errorMessage } from "../../libs/errors";
import type { CodeSampleInfo, DatasheetIntelligence, ReviewChunk, ReviewImage, ReviewScopeAudit } from "../../types";

export function useReviewDocumentDetail({
  selected,
  chunkLimit,
  onError
}: {
  selected: string;
  chunkLimit: number;
  onError: (message: string) => void;
}) {
  const [chunks, setChunks] = useState<ReviewChunk[]>([]);
  const [images, setImages] = useState<ReviewImage[]>([]);
  const [intelligence, setIntelligence] = useState<DatasheetIntelligence | null>(null);
  const [codeSample, setCodeSample] = useState<CodeSampleInfo | null>(null);
  const [scopeAudit, setScopeAudit] = useState<ReviewScopeAudit[]>([]);
  const [detailBusy, setDetailBusy] = useState(false);

  const clearDetails = () => {
    setChunks([]);
    setImages([]);
    setIntelligence(null);
    setCodeSample(null);
    setScopeAudit([]);
  };

  useEffect(() => {
    if (!selected) {
      clearDetails();
      setDetailBusy(false);
      return;
    }
    let active = true;
    setDetailBusy(true);
    clearDetails();
    onError("");
    Promise.all([getReviewDocument(selected, chunkLimit), getReviewDocumentImages(selected)])
      .then(([documentResponse, imageResponse]) => {
        if (active) {
          setChunks(documentResponse.chunks);
          setIntelligence(documentResponse.intelligence ?? null);
          setCodeSample(documentResponse.codeSample ?? null);
          setScopeAudit(documentResponse.scopeAudit || []);
          setImages(imageResponse.images);
        }
      })
      .catch((err) => {
        if (active) {
          onError(errorMessage(err, "Could not load review details"));
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
  }, [chunkLimit, onError, selected]);

  return {
    chunks,
    clearDetails,
    detailBusy,
    images,
    intelligence,
    codeSample,
    scopeAudit,
    setScopeAudit
  };
}
