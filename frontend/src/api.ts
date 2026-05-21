import type {
  AppConfig,
  DocumentChunk,
  DocumentSummary,
  QueryRequest,
  QueryResponse,
  AppSetting,
  ReviewChunk,
  ReviewDocument,
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

export function login(username: string, password: string): Promise<{ ok: boolean; username?: string; isAdmin?: boolean; token?: string; error?: string }> {
  return requestJson("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
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

export function getReviewDocument(source: string): Promise<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[] }> {
  return requestJson<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[] }>(
    `/api/review/document?source=${encodeURIComponent(source)}`
  );
}

export function approveReviewDocument(source: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/review/document/approve", {
    method: "POST",
    body: JSON.stringify({ source })
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

export function triggerIndexCheck(): Promise<{ ok: boolean; started: boolean; status: unknown }> {
  return requestJson<{ ok: boolean; started: boolean; status: unknown }>("/api/index/check", { method: "POST" });
}

export function getDocument(source: string): Promise<{ document: string; chunks: DocumentChunk[] }> {
  return requestJson<{ document: string; chunks: DocumentChunk[] }>(`/api/document?source=${encodeURIComponent(source)}`);
}

export function getTrace(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/trace");
}

export function getStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
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
