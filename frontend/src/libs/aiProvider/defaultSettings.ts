import type { AIProviderSettings } from "../../types";

export const defaultAIProviderSettings: AIProviderSettings = {
  scope: "user",
  provider: "openai",
  enabled: false,
  hasApiKey: false,
  keyPreview: "",
  keyPolicy: "user_when_available",
  assistMode: "auto",
  defaultModel: "",
  monthlyBudget: 0,
  warnPercent: 80,
  stopPercent: 100,
  pricingOverrides: []
};
