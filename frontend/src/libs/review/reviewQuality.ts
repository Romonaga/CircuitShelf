import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage } from "../../types";

export type ReviewHealthLevel = "clean" | "attention" | "blocked";

export interface ReviewHealth {
  level: ReviewHealthLevel;
  label: string;
  summary: string;
  autoApproveCandidate: boolean;
  reasons: string[];
  warnings: string[];
}

export interface ReviewEvidenceSamples {
  strongestText?: ReviewChunk;
  lowestQuality?: ReviewChunk;
  imageOcr?: ReviewChunk;
  image?: ReviewImage;
}

export function computeReviewHealth({
  chunks,
  document,
  images,
  intelligence
}: {
  chunks: ReviewChunk[];
  document: ReviewDocument;
  images: ReviewImage[];
  intelligence: DatasheetIntelligence | null;
}): ReviewHealth {
  const reasons: string[] = [];
  const warnings: string[] = [];
  const indexedChunks = document.chunkCount ?? chunks.length;
  const imageCount = document.imageCount ?? images.length;
  const storedImages = document.storedImageCount ?? imageCount;
  const extractedImages = document.extractedImageCount ?? imageCount;
  const ocrImages = document.ocrImageTextCount ?? document.indexedImageTextCount ?? 0;
  const lowQuality = document.lowQualityCount ?? chunks.filter((chunk) => chunk.quality < 0.35).length;
  const droppedChunks = document.droppedChunkCount ?? 0;
  const avgQuality = document.avgQuality ?? 0;
  const pinCount = intelligence?.pinout?.pins?.length ?? 0;

  if (document.lastError) {
    reasons.push(`Last ingest error: ${document.lastError}`);
  }
  if (indexedChunks <= 0) {
    reasons.push("No indexed text chunks were produced.");
  }
  if (lowQuality > 0) {
    warnings.push(`${lowQuality.toLocaleString()} low-quality chunks need a spot check.`);
  }
  if (droppedChunks > Math.max(4, indexedChunks * 0.08)) {
    warnings.push(`${droppedChunks.toLocaleString()} chunks were dropped during cleanup.`);
  }
  if (extractedImages > 0 && storedImages <= 0) {
    warnings.push("Images were detected but none were stored.");
  }
  if (storedImages > 0 && ocrImages <= 0) {
    warnings.push("Stored images have no indexed OCR text.");
  }
  if (intelligence?.componentName && !pinCount && /chip|timer|logic|opto|ic|micro|sensor|regulator|driver/i.test(intelligence.componentType || intelligence.summary || "")) {
    warnings.push("Component-like document has no detected pinout.");
  }

  const autoApproveCandidate = !reasons.length
    && !warnings.length
    && indexedChunks > 0
    && avgQuality >= 0.98
    && lowQuality === 0;

  if (reasons.length) {
    return {
      level: "blocked",
      label: "Needs repair",
      summary: "Do not approve until the ingestion issue is fixed or re-indexed.",
      autoApproveCandidate: false,
      reasons,
      warnings
    };
  }

  if (warnings.length) {
    return {
      level: "attention",
      label: "Review needed",
      summary: "The document indexed, but the extracted evidence deserves a quick spot check.",
      autoApproveCandidate: false,
      reasons,
      warnings
    };
  }

  return {
    level: "clean",
    label: autoApproveCandidate ? "Auto-approval candidate" : "Looks clean",
    summary: autoApproveCandidate
      ? "Clean quality, no low-quality chunks, and no extraction warnings."
      : "No blocking ingestion issues were detected.",
    autoApproveCandidate,
    reasons,
    warnings
  };
}

export function selectReviewEvidenceSamples(chunks: ReviewChunk[], images: ReviewImage[]): ReviewEvidenceSamples {
  const textChunks = chunks.filter((chunk) => chunk.preview.trim().length > 0);
  const sortedByQuality = [...textChunks].sort((left, right) => right.quality - left.quality);
  const lowQuality = [...textChunks].sort((left, right) => left.quality - right.quality)[0];
  const imageOcr = textChunks.find((chunk) => chunk.isOcr || chunk.sourceImageId);
  const image = images.find((item) => item.ocrText?.trim()) ?? images[0];

  return {
    strongestText: sortedByQuality[0],
    lowestQuality: lowQuality && lowQuality !== sortedByQuality[0] ? lowQuality : undefined,
    imageOcr,
    image
  };
}
