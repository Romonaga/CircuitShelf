import { expect, test } from "@playwright/test";

import type { ReviewDocument } from "../../types";
import {
  defaultReviewTriageFilters,
  filterReviewDocuments,
  reviewDocumentKind,
  reviewFolderOptions
} from "./reviewQueue";

function reviewDocument(overrides: Partial<ReviewDocument>): ReviewDocument {
  return {
    source: "BatchA/default.pdf",
    displayName: "Default PDF",
    status: "pending_review",
    sizeBytes: 1024,
    fileExtension: ".pdf",
    chunkCount: 12,
    imageCount: 0,
    avgQuality: 0.82,
    lowQualityCount: 0,
    ...overrides
  };
}

test("review triage filters by pdf readiness and source folder", () => {
  const documents = [
    reviewDocument({ source: "BatchA/ready.pdf", displayName: "Ready PDF" }),
    reviewDocument({ source: "BatchB/ready.pdf", displayName: "Other PDF" }),
    reviewDocument({ source: "BatchA/sketch.ino", displayName: "Sketch", fileExtension: ".ino" })
  ];

  const filtered = filterReviewDocuments(documents, {
    ...defaultReviewTriageFilters,
    kind: "pdf",
    health: "ready",
    folder: "BatchA"
  });

  expect(filtered.map((doc) => doc.source)).toEqual(["BatchA/ready.pdf"]);
});

test("review triage exposes failed metadata documents", () => {
  const documents = [
    reviewDocument({
      source: "BookDrop/MANIFEST.json",
      displayName: "MANIFEST.json",
      fileExtension: ".json",
      status: "failed",
      chunkCount: 0,
      lastError: "Unsupported file type"
    }),
    reviewDocument({ source: "BookDrop/book.pdf", displayName: "Book PDF" })
  ];

  const filtered = filterReviewDocuments(documents, {
    ...defaultReviewTriageFilters,
    kind: "metadata",
    health: "failed"
  });

  expect(filtered.map((doc) => doc.source)).toEqual(["BookDrop/MANIFEST.json"]);
});

test("review triage identifies code samples and image-bearing documents", () => {
  const documents = [
    reviewDocument({
      source: "SIM7080G_Cat_M_NB_IoT_HAT_Code/Arduino/demo/demo.ino",
      displayName: "demo.ino",
      fileExtension: ".ino"
    }),
    reviewDocument({
      source: "Books/illustrated.pdf",
      displayName: "Illustrated PDF",
      fileExtension: ".pdf",
      imageCount: 0,
      extractedImageCount: 14
    })
  ];

  expect(reviewDocumentKind(documents[0])).toBe("code");
  expect(filterReviewDocuments(documents, { ...defaultReviewTriageFilters, kind: "code" })).toEqual([documents[0]]);
  expect(filterReviewDocuments(documents, { ...defaultReviewTriageFilters, health: "with-images" })).toEqual([documents[1]]);
});

test("review triage returns sorted top-level source folders", () => {
  const documents = [
    reviewDocument({ source: "z-folder/file.pdf" }),
    reviewDocument({ source: "a-folder/file.pdf" }),
    reviewDocument({ source: "a-folder/other.pdf" }),
    reviewDocument({ source: "root.pdf" })
  ];

  expect(reviewFolderOptions(documents)).toEqual(["(root)", "a-folder", "z-folder"]);
});
