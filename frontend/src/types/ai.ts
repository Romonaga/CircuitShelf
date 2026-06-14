export interface AIModelPricing {
  provider: string;
  modelName: string;
  inputPerMillion: number;
  cachedInputPerMillion: number;
  outputPerMillion: number;
  currency: string;
  isActive: boolean;
  updatedAt?: string | null;
}

export interface AIAvailableModel {
  id: string;
  ownedBy: string;
  created: number;
}

export interface AIModelPricingOverride {
  provider?: string;
  modelName: string;
  scope?: string;
  entityId?: number | null;
  userId?: number | null;
  inputPerMillion: number;
  cachedInputPerMillion: number;
  outputPerMillion: number;
  currency?: string;
  updatedAt?: string | null;
}

export interface AIProviderSettings {
  scope: "system" | "entity" | "user" | string;
  provider: string;
  enabled: boolean;
  hasApiKey: boolean;
  hasAdminApiKey: boolean;
  keyPreview: string;
  adminKeyPreview: string;
  keyPolicy: string;
  assistMode: string;
  defaultModel: string;
  monthlyBudget: number;
  warnPercent: number;
  stopPercent: number;
  pricingOverrides: AIModelPricingOverride[];
  updatedAt?: string | null;
}

export interface AIProviderSettingsPayload {
  enabled: boolean;
  apiKey?: string;
  clearApiKey?: boolean;
  adminApiKey?: string;
  clearAdminApiKey?: boolean;
  keyPolicy?: string;
  assistMode: string;
  defaultModel: string;
  monthlyBudget: number;
  warnPercent: number;
  stopPercent: number;
  pricingOverrides?: AIModelPricingOverride[];
}

export interface AIUsageBreakdown {
  label: string;
  calls: number;
  tokens: number;
  estimatedCost: number;
}

export interface AIUsageEvent {
  id: number;
  createdAt?: string | null;
  entityId?: number | null;
  entityName?: string | null;
  userId?: number | null;
  username: string;
  provider: string;
  taskType: string;
  taskLabel: string;
  modelName: string;
  contextType: string;
  contextId: string;
  roundNumber: number;
  roundCount: number;
  inputTokens: number;
  cachedInputTokens: number;
  outputTokens: number;
  estimatedCost: number;
  finalCost?: number | null;
  billableCost: number;
  costStatus: string;
  costDiscrepancy: number;
  reconciliationRunId?: string;
  allocationMethod?: string;
  paidBy: string;
  providerKeyOwnerUserId?: number | null;
  providerKeyOwnerUsername?: string | null;
  decisionReason?: string;
  latencyMs?: number;
  success: boolean;
  errorMessage?: string | null;
}

export interface AIUsageCostPoint {
  date: string;
  calls: number;
  reconciledCalls: number;
  estimatedCost: number;
  actualCost: number;
  verifiedCost: number;
}

export interface AIUsageReport {
  summary: {
    calls: number;
    successfulCalls: number;
    tokens: number;
    inputTokens: number;
    cachedInputTokens: number;
    outputTokens: number;
    estimatedCost: number;
    billableCost: number;
    actualCost: number;
    finalCost: number;
    verifiedCost: number;
    reconciledCalls: number;
  };
  byTask: AIUsageBreakdown[];
  byUser: AIUsageBreakdown[];
  byPayer: AIUsageBreakdown[];
  byModel: AIUsageBreakdown[];
  byContext: AIUsageBreakdown[];
  costTimeline: AIUsageCostPoint[];
  events: AIUsageEvent[];
}
