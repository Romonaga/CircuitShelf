import type { DatasheetIntelligence, ReviewChunk, ReviewDocument, ReviewImage } from "../../types";

export type ReviewHealthLevel = "clean" | "attention" | "blocked";

export interface ReviewHealth {
  level: ReviewHealthLevel;
  label: string;
  summary: string;
  recommendation: ReviewRecommendation;
  autoApproveCandidate: boolean;
  reasons: string[];
  warnings: string[];
}

export interface ReviewRecommendation {
  action: string;
  detail: string;
  inspect: string[];
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
  const factCount = intelligence?.facts?.length ?? 0;
  const componentText = `${intelligence?.componentType ?? ""} ${intelligence?.summary ?? ""}`;
  const componentLike = Boolean(intelligence?.componentName)
    && /chip|timer|logic|opto|ic|micro|sensor|regulator|driver/i.test(componentText);
  const missingComponentPinout = componentLike && !pinCount;
  const hasUsefulComponentEvidence = Boolean(intelligence?.componentName) && (factCount > 0 || pinCount > 0);

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
  if (missingComponentPinout) {
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
      recommendation: buildReviewRecommendation({
        droppedChunks,
        hasUsefulComponentEvidence,
        imageCount,
        indexedChunks,
        missingComponentPinout,
        pinCount,
        reasonBlocked: true
      }),
      autoApproveCandidate: false,
      reasons,
      warnings
    };
  }

  if (warnings.length) {
    return {
      level: "attention",
      label: "Review needed",
      summary: missingComponentPinout && hasUsefulComponentEvidence
        ? "Useful component facts were found, but critical pinout evidence is incomplete."
        : "The document indexed, but the extracted evidence needs an explicit approval decision.",
      recommendation: buildReviewRecommendation({
        droppedChunks,
        hasUsefulComponentEvidence,
        imageCount,
        indexedChunks,
        missingComponentPinout,
        pinCount,
        reasonBlocked: false
      }),
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
    recommendation: buildReviewRecommendation({
      droppedChunks,
      hasUsefulComponentEvidence,
      imageCount,
      indexedChunks,
      missingComponentPinout,
      pinCount,
      reasonBlocked: false
    }),
    autoApproveCandidate,
    reasons,
    warnings
  };
}

function buildReviewRecommendation({
  droppedChunks,
  hasUsefulComponentEvidence,
  imageCount,
  indexedChunks,
  missingComponentPinout,
  pinCount,
  reasonBlocked
}: {
  droppedChunks: number;
  hasUsefulComponentEvidence: boolean;
  imageCount: number;
  indexedChunks: number;
  missingComponentPinout: boolean;
  pinCount: number;
  reasonBlocked: boolean;
}): ReviewRecommendation {
  if (reasonBlocked) {
    return {
      action: "Reprocess before approving",
      detail: "The document did not produce enough usable indexed evidence for retrieval.",
      inspect: ["source file opens correctly", "text extraction/OCR settings", "ingest error details"]
    };
  }

  if (missingComponentPinout && hasUsefulComponentEvidence) {
    return {
      action: "Keep in review",
      detail: "Do not delete solely because quality is low. Verify the part identity and pinout evidence before approval.",
      inspect: [
        "part number and manufacturer match",
        "pinout, logic diagram, or connection diagram",
        "electrical ratings and absolute maximums",
        "package facts match the physical part",
        imageCount > 0 ? "OCR image pages" : "source pages around pin tables",
        droppedChunks > 0 ? "dropped-chunk summary" : "lowest-quality chunks"
      ]
    };
  }

  if (missingComponentPinout) {
    return {
      action: "Inspect pinout evidence",
      detail: "The document looks component-like, but no normalized pins were found.",
      inspect: ["pinout or terminal-function table", "OCR image pages", "package-specific pin diagrams"]
    };
  }

  if (indexedChunks > 0) {
    return {
      action: pinCount > 0 ? "Approve after spot check" : "Spot check then approve",
      detail: "The document has indexed evidence; confirm the warning items before making it retrievable.",
      inspect: ["strongest text sample", "lowest-quality text sample", "image OCR coverage"]
    };
  }

  return {
    action: "Reject or reprocess",
    detail: "No useful indexed evidence is available.",
    inspect: ["source file quality", "OCR settings", "upload format"]
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
