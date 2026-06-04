import type { AccountProfile, AIModelPricing, AIProviderSettings, AIProviderSettingsPayload, AIUsageReport } from "../../types";
import { requestJson } from "./core";

export function updateAccountProfile(payload: Partial<AccountProfile>): Promise<{ profile: AccountProfile }> {
  return requestJson<{ profile: AccountProfile }>("/api/account/profile", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function updateAccountPassword(payload: { currentPassword: string; newPassword: string }): Promise<{ ok: boolean }> {
  return requestJson<{ ok: boolean }>("/api/account/password", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getAccountAIProvider(): Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }> {
  return requestJson<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>("/api/account/ai-provider");
}

export function getAccountAIProviderModels(): Promise<{ models: import("../../types").AIAvailableModel[] }> {
  return requestJson<{ models: import("../../types").AIAvailableModel[] }>("/api/account/ai-provider/models");
}

export function updateAccountAIProvider(payload: AIProviderSettingsPayload): Promise<{ settings: AIProviderSettings }> {
  return requestJson<{ settings: AIProviderSettings }>("/api/account/ai-provider", {
    method: "PUT",
    body: JSON.stringify(payload)
  });
}

export function getAccountAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/account/ai-usage?days=${encodeURIComponent(String(days))}`);
}
