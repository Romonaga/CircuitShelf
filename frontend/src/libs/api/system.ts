import type { AIAvailableModel, AIModelPricing, AIProviderSettings, AIProviderSettingsPayload, AIUsageReport, AppSetting, LogTailPayload, PasswordPolicy, PerformanceReport, RuntimeCatalog, StatusPayload } from "../../types";
import { requestJson } from "./core";

export function getSystemPasswordPolicy(): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/system/password-policy");
}

export function updateSystemPasswordPolicy(policy: PasswordPolicy): Promise<{ policy: PasswordPolicy }> {
  return requestJson<{ policy: PasswordPolicy }>("/api/system/password-policy", {
    method: "PUT",
    body: JSON.stringify(policy)
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

export function getSystemAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/system/ai-usage?days=${encodeURIComponent(String(days))}`);
}

export function getRuntimeCatalog(): Promise<RuntimeCatalog> {
  return requestJson<RuntimeCatalog>("/api/runtime/catalog");
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
