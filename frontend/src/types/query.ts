import type { CircuitBuildCard, SourceSummary } from "./documents";

export type RetrievalStrategy = "Vector only" | "Vector + CrossEncoder" | string;

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
  conversationId?: string | null;
}

export type ChatTurn = [string, string];

export interface ConversationTurn {
  id: string;
  ordinal: number;
  question: string;
  answer: string;
  modelName?: string | null;
  retrievalStrategy?: string | null;
  confidence?: number | null;
  responseSnapshot?: Partial<QueryResponse> | null;
  createdAt?: string | null;
}

export interface ConversationSummary {
  id: string;
  userId?: number | null;
  username?: string | null;
  title: string;
  turnCount: number;
  createdAt?: string | null;
  updatedAt?: string | null;
  lastTurnAt?: string | null;
}

export interface ConversationDetail extends ConversationSummary {
  turns: ConversationTurn[];
}

export interface QueryResponse {
  conversation?: ConversationDetail | null;
  question: string;
  answer: string;
  chatHistory: ChatTurn[];
  contextChatHistory?: ChatTurn[];
  sources: SourceSummary[];
  buildCard?: CircuitBuildCard | null;
  validation?: ResponseValidation | null;
  cacheStats: unknown;
  confidence: number | null;
  averageQueryTime: number | null;
  error?: string;
}

export interface ResponseValidation {
  enabled: boolean;
  ran: boolean;
  useful: boolean;
  changed: boolean;
  confidence?: number | null;
  issues: string[];
  notes: string[];
  elapsedMs: number;
  model?: string | null;
}
