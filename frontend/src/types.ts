export type RetrievalStrategy = "FAISS only" | "FAISS + CrossEncoder" | string;
export type View = "ask" | "documents" | "trace" | "status";

export interface AppConfig {
  siteName: string;
  models: string[];
  defaultModel: string;
  authConfigured: boolean;
  retrievalStrategies: RetrievalStrategy[];
  defaults: QueryOptions;
}

export interface QueryOptions {
  topK: number;
  distanceThreshold: number;
  maxTokens: number;
  showFullText: boolean;
  bypassCache: boolean;
  strategy: RetrievalStrategy;
}

export interface QueryRequest extends QueryOptions {
  question: string;
  model: string;
  chatHistory: ChatTurn[];
}

export type ChatTurn = [string, string];

export interface QueryResponse {
  question: string;
  answer: string;
  chatHistory: ChatTurn[];
  sources: SourceSummary[];
  cacheStats: unknown;
  confidence: number | null;
  averageQueryTime: number | null;
  error?: string;
}

export interface DocumentSummary {
  source: string;
  displayName?: string;
  chunkCount: number;
  imageCount: number;
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
  sourceImageId?: string | null;
  tokens: number;
  preview: string;
}

export interface StatusPayload {
  chunks: number;
  sources: number;
  embeddings: number;
  faissTotal: number;
  vectorChunks?: number;
  vectorEmbeddings?: number;
  imageIds: number;
  imageFaissTotal: number;
  cacheStats: unknown;
}
