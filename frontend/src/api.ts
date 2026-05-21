import type {
  AppConfig,
  DocumentChunk,
  DocumentSummary,
  QueryRequest,
  QueryResponse,
  StatusPayload
} from "./types";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    },
    ...init
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

export function getAppConfig(): Promise<AppConfig> {
  return requestJson<AppConfig>("/api/app-config");
}

export function login(username: string, password: string): Promise<{ ok: boolean; username?: string; error?: string }> {
  return requestJson("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
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

export function getDocument(source: string): Promise<{ document: string; chunks: DocumentChunk[] }> {
  return requestJson<{ document: string; chunks: DocumentChunk[] }>(`/api/document?source=${encodeURIComponent(source)}`);
}

export function getTrace(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/trace");
}

export function getStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
}
