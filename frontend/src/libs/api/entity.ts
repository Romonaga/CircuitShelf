import type {
  AIAvailableModel,
  AIModelPricing,
  AIProviderSettings,
  AIProviderSettingsPayload,
  EntityContext,
  EntityMember,
  PasswordPolicy
} from "../../types";
import { requestJson } from "./core";

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
