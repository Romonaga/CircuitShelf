import type { AIUsageReport } from "../../types";
import { readSessionToken, requestJson } from "./core";

export function getEntityAIUsage(days = 31): Promise<AIUsageReport> {
  return requestJson<AIUsageReport>(`/api/entity/ai-usage?days=${encodeURIComponent(String(days))}`);
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
