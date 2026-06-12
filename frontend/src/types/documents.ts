export interface DocumentSummary {
  source: string;
  displayName?: string;
  chunkCount: number;
  imageCount: number;
  rawChunkCount?: number;
  droppedChunkCount?: number;
  extractedImageCount?: number;
  storedImageCount?: number;
  indexedImageTextCount?: number;
  ocrImageTextCount?: number;
}

export interface UploadedDocument {
  filename: string;
  bytes: number;
}

export interface SkippedDocumentUpload {
  filename: string;
  reason: string;
}

export interface UploadDocumentsResponse {
  ok: boolean;
  files: UploadedDocument[];
  skippedFiles: SkippedDocumentUpload[];
  count: number;
  skippedCount: number;
  bytes: number;
  filename?: string;
  indexing: {
    started: boolean;
    status?: unknown;
  };
}

export interface RemoveDocumentResponse {
  ok: boolean;
  document?: {
    source_path?: string;
    display_name?: string;
  };
  deletedFile: boolean;
}

export interface SourceChunk {
  index?: number | null;
  page?: number | string | null;
  section?: string;
  category?: string;
  distance?: number | null;
  sourceImageId?: string | null;
  preview?: string;
}

export interface SourceSummary {
  source: string;
  displayName?: string;
  pages?: Array<number | string>;
  chunkCount?: number;
  chunks?: SourceChunk[];
}

export interface DocumentChunk {
  index: number;
  section: string;
  category: string;
  page?: number | string | null;
  chunkType?: string;
  sourceImageId?: string | null;
  tokens: number;
  preview: string;
}

export interface DocumentImage {
  imageKey: string;
  caption: string;
  page?: number | string | null;
  imageMimeType?: string;
  imageBase64: string;
  ocrText?: string;
}

export interface DocumentPage {
  page: number | string;
  chunks: DocumentChunk[];
  images: DocumentImage[];
}

export interface DocumentPin {
  pin: number;
  label: string;
  function: string;
  page?: number | string | null;
  chunkIndex?: number | null;
}

export interface DocumentPinout {
  source: string;
  displayName: string;
  pins: DocumentPin[];
}

export interface DatasheetFact {
  type: string;
  label: string;
  value: string;
  unit?: string;
  page?: number | string | null;
  chunkIndex?: number | null;
  evidence?: string;
  confidence?: number;
}

export interface DatasheetIntelligence {
  source: string;
  displayName: string;
  componentName: string;
  componentType: string;
  summary: string;
  confidence: number;
  facts: DatasheetFact[];
  pinout: DocumentPinout;
  updatedAt?: string | null;
}

export interface CodeSampleInfo {
  packKey: string;
  packDisplayName: string;
  rootPath?: string;
  summary?: string;
  relativePath: string;
  language: string;
  role?: string;
  board?: string;
  framework?: string;
  libraries: string[];
  components: string[];
  interfaces: string[];
  pins: Array<{ name: string; pin: string }>;
  updatedAt?: string | null;
}

export interface CircuitBuildCard {
  title: string;
  componentName: string;
  componentType: string;
  summary: string;
  confidence: number;
  parts: Array<{ name: string; detail: string }>;
  power: string[];
  wiring: Array<{ from: string; to: string; note: string; page?: number | string | null }>;
  checks: string[];
  warnings: string[];
  sourceNotes: Array<{ source: string; pages: Array<number | string>; chunks: number }>;
}

export interface DocumentDetail {
  document: string;
  displayName: string;
  chunks: DocumentChunk[];
  images: DocumentImage[];
  pages: DocumentPage[];
  pinout: DocumentPinout;
  intelligence?: DatasheetIntelligence | null;
  codeSample?: CodeSampleInfo | null;
  ingestStats?: DocumentIngestStats | null;
}

export interface DocumentIngestStats {
  rawChunkCount: number;
  chunkCount: number;
  droppedChunkCount: number;
  extractedImageCount: number;
  storedImageCount: number;
  indexedImageTextCount: number;
  ocrImageTextCount: number;
}
