import type {
  AppConfig,
  AccountProfile,
  AssemblyLearningSession,
  AssemblyPlan,
  AssemblyPlanExport,
  AssemblyPhotoCheck,
  AssemblyPlanSummary,
  AssemblyStepEvidence,
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
  DatasheetIntelligence,
  ReviewImage,
  ReviewScopeAudit,
  RuntimeCatalog,
  LogTailPayload,
  InventoryPart,
  InventoryPartInput,
  InventoryImportItem,
  InventoryImportPreview,
  ProjectFinderResponse,
  PerformanceReport,
  StatusPayload,
  EntityContext,
  EntityMember,
  PasswordPolicy,
  AIAvailableModel,
  AIModelPricing,
  AIProviderSettings,
  AIProviderSettingsPayload,
  AIUsageReport,
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

export function login(username: string, password: string): Promise<{ ok: boolean; userId?: number; username?: string; isAdmin?: boolean; canManageSystem?: boolean; forcePasswordChange?: boolean; entity?: EntityContext | null; token?: string; error?: string }> {
  return requestJson("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export function getMe(): Promise<{ userId?: number; username: string; isAdmin: boolean; canManageSystem?: boolean; forcePasswordChange?: boolean; entity?: EntityContext | null; profile?: AccountProfile | null }> {
  return requestJson("/api/me");
}

export function updateAccountProfile(payload: Partial<AccountProfile>): Promise<{ profile: AccountProfile }> {
  return requestJson<{ profile: AccountProfile }>("/api/account/profile", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getCurrentEntity(): Promise<{ entity: EntityContext; user: unknown }> {
  return requestJson<{ entity: EntityContext; user: unknown }>("/api/entity/current");
}

export function getEntityMembers(): Promise<{ entity: EntityContext; members: EntityMember[] }> {
  return requestJson<{ entity: EntityContext; members: EntityMember[] }>("/api/entity/members");
}

export function createEntityMember(payload: {
  username: string;
  temporaryPassword: string;
  email?: string;
  displayName?: string;
  nickname?: string;
  phone?: string;
  address?: string;
  role: string;
  forcePasswordChange: boolean;
}): Promise<{ ok: boolean; members: EntityMember[] }> {
  return requestJson<{ ok: boolean; members: EntityMember[] }>("/api/entity/members", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function updateEntityMemberRole(userId: number, role: string): Promise<{ ok: boolean; members: EntityMember[] }> {
  return requestJson<{ ok: boolean; members: EntityMember[] }>(`/api/entity/members/${encodeURIComponent(String(userId))}/role`, {
    method: "PUT",
    body: JSON.stringify({ role })
  });
}

export function unlockEntityMember(userId: number): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/entity/members/${encodeURIComponent(String(userId))}/unlock`, {
    method: "POST"
  });
}

export function disableEntityMember(userId: number, reason: string): Promise<{ ok: boolean; members: EntityMember[] }> {
  return requestJson<{ ok: boolean; members: EntityMember[] }>(`/api/entity/members/${encodeURIComponent(String(userId))}/disable`, {
    method: "POST",
    body: JSON.stringify({ reason })
  });
}

export function enableEntityMember(userId: number): Promise<{ ok: boolean; members: EntityMember[] }> {
  return requestJson<{ ok: boolean; members: EntityMember[] }>(`/api/entity/members/${encodeURIComponent(String(userId))}/enable`, {
    method: "POST"
  });
}

export function resetEntityMemberPassword(
  userId: number,
  payload: { temporaryPassword: string; forcePasswordChange: boolean }
): Promise<{ ok: boolean; members: EntityMember[] }> {
  return requestJson<{ ok: boolean; members: EntityMember[] }>(`/api/entity/members/${encodeURIComponent(String(userId))}/reset-password`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function forceEntityMemberPasswordChange(userId: number): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/entity/members/${encodeURIComponent(String(userId))}/force-password-change`, {
    method: "POST"
  });
}

export function getEntityPasswordPolicy(): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/entity/password-policy");
}

export function updateEntityPasswordPolicy(policy: PasswordPolicy): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/entity/password-policy", {
    method: "PUT",
    body: JSON.stringify(policy)
  });
}

export function getSystemPasswordPolicy(): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/system/password-policy");
}

export function updateSystemPasswordPolicy(policy: PasswordPolicy): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/system/password-policy", {
    method: "PUT",
    body: JSON.stringify(policy)
  });
}

export function getAccountAIProvider(): Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }> {
  return requestJson<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>("/api/account/ai-provider");
}

export function getAccountAIProviderModels(): Promise<{ models: AIAvailableModel[] }> {
  return requestJson<{ models: AIAvailableModel[] }>("/api/account/ai-provider/models");
}

export function updateAccountAIProvider(payload: AIProviderSettingsPayload): Promise<{ settings: AIProviderSettings }> {
  return requestJson<{ settings: AIProviderSettings }>("/api/account/ai-provider", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getEntityAIProvider(): Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }> {
  return requestJson<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>("/api/entity/ai-provider");
}

export function getEntityAIProviderModels(): Promise<{ models: AIAvailableModel[] }> {
  return requestJson<{ models: AIAvailableModel[] }>("/api/entity/ai-provider/models");
}

export function updateEntityAIProvider(payload: AIProviderSettingsPayload): Promise<{ settings: AIProviderSettings }> {
  return requestJson<{ settings: AIProviderSettings }>("/api/entity/ai-provider", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getSystemAIProvider(): Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }> {
  return requestJson<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>("/api/system/ai-provider");
}

export function getSystemAIProviderModels(): Promise<{ models: AIAvailableModel[] }> {
  return requestJson<{ models: AIAvailableModel[] }>("/api/system/ai-provider/models");
}

export function updateSystemAIProvider(payload: AIProviderSettingsPayload): Promise<{ settings: AIProviderSettings }> {
  return requestJson<{ settings: AIProviderSettings }>("/api/system/ai-provider", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getEntityAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/entity/ai-usage?days=${encodeURIComponent(String(days))}`);
}

export function getSystemAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/system/ai-usage?days=${encodeURIComponent(String(days))}`);
}

export function getRuntimeCatalog(): Promise<RuntimeCatalog> {
  return requestJson<RuntimeCatalog>("/api/runtime/catalog");
}

export function getAccountAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/account/ai-usage?days=${encodeURIComponent(String(days))}`);
}

export async function downloadAIUsageCsv(scope: "entity" | "system" | "personal", days = 31): Promise<Blob> {
  const session = readSessionToken();
  const path = scope === "system"
    ? "/api/system/ai-usage/export"
    : scope === "personal"
      ? "/api/account/ai-usage/export"
      : "/api/entity/ai-usage/export";
  const response = await fetch(`${path}?days=${encodeURIComponent(String(days))}`, {
    headers: {
      ...(session ? { Authorization: `Bearer ${session}` } : {})
    }
  });
  if (response.status === 401) {
    window.dispatchEvent(new CustomEvent("circuitshelf-auth-expired"));
  }
  if (!response.ok) {
    const raw = await response.text();
    throw new Error(raw || response.statusText || "Could not export AI usage");
  }
  return response.blob();
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

export function updateAccountPassword(payload: { currentPassword: string; newPassword: string }): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/account/password", {
    method: "PUT",
    body: JSON.stringify(payload)
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

export function deleteAssemblyPlan(planId: string): Promise<{ ok: boolean; deleted?: { id: string; title: string } }> {
  return requestJson<{ ok: boolean; deleted?: { id: string; title: string } }>(`/api/assembly-plans/${encodeURIComponent(planId)}`, {
    method: "DELETE"
  });
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

export function getAssemblyStepEvidence(planId: string, stepId: string): Promise<AssemblyStepEvidence> {
  return requestJson<AssemblyStepEvidence>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/steps/${encodeURIComponent(stepId)}/evidence`
  );
}

export function exportAssemblyPlan(planId: string, format: string): Promise<AssemblyPlanExport> {
  return requestJson<AssemblyPlanExport>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/export?format=${encodeURIComponent(format)}`
  );
}

export function getAssemblyLearning(planId: string): Promise<{ learning: AssemblyLearningSession }> {
  return requestJson<{ learning: AssemblyLearningSession }>(`/api/assembly-plans/${encodeURIComponent(planId)}/learning`);
}

export function updateAssemblyLearning(planId: string, action: string): Promise<{ learning: AssemblyLearningSession }> {
  return requestJson<{ learning: AssemblyLearningSession }>(`/api/assembly-plans/${encodeURIComponent(planId)}/learning`, {
    method: "PATCH",
    body: JSON.stringify({ action })
  });
}

export function submitAssemblyPhotoCheck(planId: string, file: File, note: string): Promise<{ check: AssemblyPhotoCheck; checks: AssemblyPhotoCheck[] }> {
  const body = new FormData();
  body.append("file", file);
  body.append("note", note);
  return requestJson<{ check: AssemblyPhotoCheck; checks: AssemblyPhotoCheck[] }>(
    `/api/assembly-plans/${encodeURIComponent(planId)}/photo-check`,
    {
      method: "POST",
      body,
      headers: {}
    }
  );
}

export function getAssemblyPhotoChecks(planId: string): Promise<{ checks: AssemblyPhotoCheck[] }> {
  return requestJson<{ checks: AssemblyPhotoCheck[] }>(`/api/assembly-plans/${encodeURIComponent(planId)}/photo-checks`);
}

export function getInventoryParts(): Promise<{ parts: InventoryPart[] }> {
  return requestJson<{ parts: InventoryPart[] }>("/api/inventory/parts");
}

export function saveInventoryPart(part: InventoryPartInput): Promise<{ part: InventoryPart }> {
  return requestJson<{ part: InventoryPart }>("/api/inventory/parts", {
    method: "POST",
    body: JSON.stringify(part)
  });
}

export function deleteInventoryPart(partId: string): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>(`/api/inventory/parts/${encodeURIComponent(partId)}`, {
    method: "DELETE"
  });
}

export function previewInventoryImport(text: string): Promise<InventoryImportPreview> {
  return requestJson<InventoryImportPreview>("/api/inventory/import/preview", {
    method: "POST",
    body: JSON.stringify({ text })
  });
}

export function applyInventoryImport(items: InventoryImportItem[]): Promise<{ parts: InventoryPart[]; count: number }> {
  return requestJson<{ parts: InventoryPart[]; count: number }>("/api/inventory/import/apply", {
    method: "POST",
    body: JSON.stringify({ items })
  });
}

export function getProjectCandidates(limit = 24): Promise<ProjectFinderResponse> {
  return requestJson<ProjectFinderResponse>(`/api/inventory/project-candidates?limit=${encodeURIComponent(String(limit))}`);
}

export function getDocuments(scope = "visible"): Promise<{ documents: DocumentSummary[] }> {
  return requestJson<{ documents: DocumentSummary[] }>(`/api/documents?scope=${encodeURIComponent(scope)}`);
}

export interface UploadProgress {
  loaded: number;
  total: number;
  percent: number;
  computable: boolean;
  bytesPerSecond?: number | null;
  etaSeconds?: number | null;
  elapsedSeconds?: number | null;
}

export function uploadDocuments(
  files: File[],
  overwrite: boolean,
  scope = "entity",
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const totalBytes = files.reduce((sum, file) => sum + file.size, 0);
  const batches = splitUploadBatches(files);
  if (batches.length > 1) {
    return uploadDocumentBatches(batches, overwrite, scope, totalBytes, onProgress);
  }
  return uploadDocumentBatch(files, overwrite, scope, false, totalBytes, 0, performance.now(), onProgress);
}

function splitUploadBatches(files: File[]): File[][] {
  const maxFiles = 6;
  const maxBytes = 96 * 1024 * 1024;
  const batches: File[][] = [];
  let current: File[] = [];
  let currentBytes = 0;
  for (const file of files) {
    const wouldOverflow = current.length > 0 && (current.length >= maxFiles || currentBytes + file.size > maxBytes);
    if (wouldOverflow) {
      batches.push(current);
      current = [];
      currentBytes = 0;
    }
    current.push(file);
    currentBytes += file.size;
  }
  if (current.length) {
    batches.push(current);
  }
  return batches;
}

async function uploadDocumentBatches(
  batches: File[][],
  overwrite: boolean,
  scope: string,
  totalBytes: number,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const startedAt = performance.now();
  const aggregate: UploadDocumentsResponse = {
    ok: true,
    files: [],
    skippedFiles: [],
    count: 0,
    skippedCount: 0,
    bytes: 0,
    indexing: { started: false }
  };
  let completedBytes = 0;

  for (const batch of batches) {
    const batchTotal = batch.reduce((sum, file) => sum + file.size, 0);
    const result = await uploadDocumentBatch(batch, overwrite, scope, true, totalBytes, completedBytes, startedAt, onProgress);
    aggregate.files.push(...(result.files ?? []));
    aggregate.skippedFiles.push(...(result.skippedFiles ?? []));
    aggregate.count += result.count ?? 0;
    aggregate.skippedCount += result.skippedCount ?? 0;
    aggregate.bytes += result.bytes ?? 0;
    completedBytes += batchTotal;
  }

  if (aggregate.count > 0) {
    aggregate.indexing = await triggerIndexCheck();
  }
  return aggregate;
}

function uploadDocumentBatch(
  files: File[],
  overwrite: boolean,
  scope: string,
  deferIndex: boolean,
  totalBytes: number,
  completedBytes: number,
  startedAt: number,
  onProgress?: (progress: UploadProgress) => void
): Promise<UploadDocumentsResponse> {
  const body = new FormData();
  files.forEach((file) => body.append("files", file, file.webkitRelativePath || file.name));
  const session = readSessionToken();
  const path = `/api/documents/upload-batch?overwrite=${overwrite ? "true" : "false"}&scope=${encodeURIComponent(scope)}&defer_index=${deferIndex ? "true" : "false"}`;

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    if (session) {
      xhr.setRequestHeader("Authorization", `Bearer ${session}`);
    }

    xhr.upload.onprogress = (event) => {
      const total = totalBytes || (event.lengthComputable ? event.total : files.reduce((sum, file) => sum + file.size, 0));
      const loaded = Math.min(total, completedBytes + event.loaded);
      const elapsedSeconds = Math.max((performance.now() - startedAt) / 1000, 0);
      const bytesPerSecond = elapsedSeconds > 0.2 ? loaded / elapsedSeconds : null;
      const etaSeconds = bytesPerSecond && total > loaded ? (total - loaded) / bytesPerSecond : null;
      onProgress?.({
        loaded,
        total,
        percent: total > 0 ? Math.min(100, Math.round((loaded / total) * 100)) : 0,
        computable: event.lengthComputable,
        bytesPerSecond,
        etaSeconds,
        elapsedSeconds
      });
    };

    xhr.onload = () => {
      let data: UploadDocumentsResponse & { error?: string };
      try {
        data = xhr.responseText
          ? (JSON.parse(xhr.responseText) as UploadDocumentsResponse & { error?: string })
          : ({} as UploadDocumentsResponse & { error?: string });
      } catch {
        reject(new Error(`Expected JSON from ${path}, got ${xhr.status}: ${xhr.responseText.slice(0, 160)}`));
        return;
      }

      if (xhr.status === 401) {
        window.dispatchEvent(new Event("circuitshelf-auth-expired"));
      }
      if (xhr.status < 200 || xhr.status >= 300 || data.error) {
        reject(new Error(data.error || `Upload failed with status ${xhr.status}`));
        return;
      }
      resolve(data);
    };

    xhr.onerror = () => reject(new Error("Upload failed due to a network error."));
    xhr.onabort = () => reject(new Error("Upload was cancelled."));
    xhr.send(body);
  });
}

export function getReviewDocuments(): Promise<{ documents: ReviewDocument[] }> {
  return requestJson<{ documents: ReviewDocument[] }>("/api/review/documents");
}

export function getReviewDocument(
  source: string,
  limit = 50
): Promise<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[]; scopeAudit?: ReviewScopeAudit[]; intelligence?: DatasheetIntelligence | null }> {
  return requestJson<{ document: string; displayName?: string; status?: string; chunks: ReviewChunk[]; scopeAudit?: ReviewScopeAudit[]; intelligence?: DatasheetIntelligence | null }>(
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

export function updateReviewDocumentScope(source: string, scope: "global" | "entity", reason: string): Promise<{ ok: boolean; scopeAudit?: ReviewScopeAudit[] }> {
  return requestJson<{ ok: boolean; scopeAudit?: ReviewScopeAudit[] }>("/api/review/document/scope", {
    method: "POST",
    body: JSON.stringify({ source, scope, reason })
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

export function getDocument(source: string, scope = "visible"): Promise<DocumentDetail> {
  return requestJson<DocumentDetail>(`/api/document?source=${encodeURIComponent(source)}&scope=${encodeURIComponent(scope)}`);
}

export function getTrace(): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>("/api/trace");
}

export function getStatus(): Promise<StatusPayload> {
  return requestJson<StatusPayload>("/api/status");
}

export function getPerformanceReport(hours = 24): Promise<PerformanceReport> {
  return requestJson<PerformanceReport>(`/api/performance?hours=${encodeURIComponent(String(hours))}`);
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
