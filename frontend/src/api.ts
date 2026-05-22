import type {
  AppConfig,
  AssemblyPlan,
  AssemblyPlanSummary,
  BuildAssemblyPlanResponse,
  ConversationDetail,
  ConversationSummary,
  DocumentDetail,
  DocumentSummary,
  QueryRequest,
  QueryResponse,
  AppSetting,
  RemoveDocumentResponse,
  ReviewChunk,
  ReviewDocument,
  ReviewImage,
  LogTailPayload,
  StatusPayload,
  UploadDocumentsResponse
} from "./types";

const sessionStorageKey = "circuitshelf-session";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const session = readSessionToken();
  const isFormData = init?.body instanceof FormData;
  const { headers: initHeaders, ...requestInit } = init ?? {};
  const response = await fetch(path, {
    ...requestInit,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(session ? { Authorization: `Bearer ${session}` } : {}),
      ...(initHeaders ?? {})
    }
  });

  const raw = await response.text();
  let data: T & { error?: string };
  try {
    data = raw ? (JSON.parse(raw) as T & { error?: string }) : ({} as T & { error?: string });
  } catch {
    const preview = raw.trim().slice(0, 160) || response.statusText;
    throw new Error(`Expected JSON from ${path}, got ${response.status} ${response.statusText}: ${preview}`);
  }

  if (!response.ok || data.error) {
    if (response.status === 401) {
      window.dispatchEvent(new Event("circuitshelf-auth-expired"));
    }
    throw new Error(data.error || `Request failed with status ${response.status}`);
  }
  return data as T;
}

function readSessionToken(): string {
  try {
    const raw = window.localStorage.getItem(sessionStorageKey);
    if (!raw) {
      return "";
    }
    const session = JSON.parse(raw) as { token?: string };
    return session.token || "";
  } catch {
    return "";
  }
}

export function getAppConfig(): Promise<AppConfig> {
  return requestJson<AppConfig>("/api/app-config");
}

export function login(username: string, password: string): Promise<{ ok: boolean; userId?: number; username?: string; isAdmin?: boolean; token?: string; error?: string }> {
  return requestJson("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export function getUserPreference<T>(key: string): Promise<{ key: string; value: T }> {
  return requestJson<{ key: string; value: T }>(`/api/user/preferences/${encodeURIComponent(key)}`);
}

export function updateUserPreference<T>(key: string, value: T): Promise<{ key: string; value: T }> {
  return requestJson<{ key: string; value: T }>(`/api/user/preferences/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value })
  });
}

export function logout(): Promise<{ ok: boolean }> {
  return requestJson("/api/logout", { method: "POST" });
}

export function runQuery(payload: QueryRequest): Promise<QueryResponse> {
  return requestJson<QueryResponse>("/api/query", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function getConversations(): Promise<{ conversations: ConversationSummary[] }> {
  return requestJson<{ conversations: ConversationSummary[] }>("/api/conversations");
}

export function createConversation(title = "New conversation"): Promise<{ conversation: ConversationDetail }> {
  return requestJson<{ conversation: ConversationDetail }>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export function getConversation(conversationId: string): Promise<{ conversation: ConversationDetail }> {
  return requestJson<{ conversation: ConversationDetail }>(`/api/conversations/${encodeURIComponent(conversationId)}`);
}

export function deleteConversation(conversationId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE"
  });
}

export function getAssemblyPlans(): Promise<{ plans: AssemblyPlanSummary[] }> {
  return requestJson<{ plans: AssemblyPlanSummary[] }>("/api/assembly-plans");
}

export function getAssemblyPlan(planId: string): Promise<{ plan: AssemblyPlan }> {
  return requestJson<{ plan: AssemblyPlan }>(`/api/assembly-plans/${encodeURIComponent(planId)}`);
}

export function buildAssemblyPlan(payload: {
  objective: string;
  model: string;
  topK: number;
  distanceThreshold: number;
  maxTokens: number;
  strategy: string;
}): Promise<BuildAssemblyPlanResponse> {
  return requestJson<BuildAssemblyPlanResponse>("/api/assembly-plans/build", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateAssemblyStep(planId: string, stepId: string, completed: boolean): Promise<{ plan: AssemblyPlan }> {
  return requestJson<{ plan: AssemblyPlan }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}`,
    {
      method: "PATCH",
      body: JSON.stringify({ completed })
    }
  );
}

export function askAssemblyAssistant(planId: string, message: string, model: string): Promise<{ plan: AssemblyPlan; answer: string }> {
  return requestJson<{ plan: AssemblyPlan; answer: string }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/assistant`,
    {
      method: "POST",
      body: JSON.stringify({ message, model })
    }
  );
}

export function getDocuments(): Promise<{ documents: DocumentSummary[] }> {
  return requestJson<{ documents: DocumentSummary[] }>("/api/documents");
}

export function uploadDocuments(files: File[], overwrite: boolean): Promise<UploadDocumentsResponse> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file));
  return requestJson<UploadDocumentsResponse>(
    `/api/documents/upload-batch?overwrite=${overwrite ? "true" : "false"}`,
    {
      method: "POST",
      body,
      headers: {}
    }
  );
}

export function getReviewDocuments(): Promise<{ documents: ReviewDocument[] }> {
  return requestJson<{ documents: ReviewDocument[] }>("/api/review/documents");
}

export function getReviewDocument(source: string, limit = 50): Promise<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[] }> {
  return requestJson<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[] }>(
    `/api/review/document?source=${encodeURIComponent(source)}&limit=${encodeURIComponent(String(limit))}`
  );
}

export function getReviewDocumentImages(source: string): Promise<{ document: string; images: ReviewImage[] }> {
  return requestJson<{ document: string; images: ReviewImage[] }>(
    `/api/review/document/images?source=${encodeURIComponent(source)}`
  );
}

export function approveReviewDocument(source: string, includeImages = true): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/approve", {
    method: "POST",
    body: JSON.stringify({ source, includeImages })
  });
}

export function reindexReviewDocument(source: string): Promise<{ ok: boolean; chunks: number; droppedChunks: number; images: number }> {
  return requestJson<{ ok: boolean; chunks: number; droppedChunks: number; images: number }>("/api/review/document/reindex", {
    method: "POST",
    body: JSON.stringify({ source })
  });
}

export function removeReviewDocument(source: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/remove", {
    method: "POST",
    body: JSON.stringify({ source, deleteFile: true })
  });
}

export function removeIndexedDocument(source: string): Promise<RemoveDocumentResponse> {
  return requestJson<RemoveDocumentResponse>("/api/document/remove", {
    method: "POST",
    body: JSON.stringify({ source, deleteFile: true })
  });
}

export function triggerIndexCheck(): Promise<{ ok: boolean; started: boolean; status: unknown }> {
  return requestJson<{ ok: boolean; started: boolean; status: unknown }>("/api/index/check", { method: "POST" });
}

export function getDocument(source: string): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(`/api/document?source=${encodeURIComponent(source)}`);
}

export function getTrace(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/trace");
}

export function getStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
}

export function getStatusLogTail(lines = 200): Promise<LogTailPayload> {
  return requestJson<LogTailPayload>(`/api/status/log-tail?lines=${encodeURIComponent(String(lines))}`);
}

export function getSettings(): Promise<{ settings: AppSetting[] }> {
  return requestJson<{ settings: AppSetting[] }>("/api/settings");
}

export function updateSetting(key: string, value: AppSetting["value"]): Promise<{ setting: AppSetting }> {
  return requestJson<{ setting: AppSetting }>(`/api/settings/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value })
  });
}

export { sessionStorageKey };
