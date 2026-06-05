import type { AIUsageScope } from "../hooks/useAIUsageReport";

export const AI_USAGE_SCOPE_COPY: Record<AIUsageScope, { label: string; description: string }> = {
  system: {
    label: "System",
    description: "All system-paid, entity-paid, and personal AI calls visible to CircuitShelf system admins."
  },
  entity: {
    label: "Entity",
    description: "AI calls for this entity. Entity owners and admins can audit entity-paid usage and member activity."
  },
  personal: {
    label: "Personal",
    description: "Your own AI calls and personal key usage. Regular users only see this scope."
  }
};

export function allowedAIUsageScopes(canManageSystem: boolean, canManageEntity: boolean): AIUsageScope[] {
  if (canManageSystem) {
    return ["system", "entity", "personal"];
  }
  if (canManageEntity) {
    return ["entity", "personal"];
  }
  return ["personal"];
}

export function defaultAIUsageScope(canManageSystem: boolean, canManageEntity: boolean): AIUsageScope {
  return allowedAIUsageScopes(canManageSystem, canManageEntity)[0];
}
