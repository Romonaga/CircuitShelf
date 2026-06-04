import type { AIAvailableModel, AIModelPricing } from "../../types";

export interface AIModelOption {
  id: string;
  source: "catalog" | "account";
  priced: boolean;
  ownedBy: string;
  created: number;
}

export function buildModelOptions({
  availableModels,
  defaultModel,
  pricing
}: {
  availableModels: AIAvailableModel[];
  defaultModel: string;
  pricing: AIModelPricing[];
}): AIModelOption[] {
  const byId = new Map<string, AIModelOption>();
  pricing.forEach((item) => {
    byId.set(item.modelName, {
      id: item.modelName,
      source: "catalog",
      priced: true,
      ownedBy: "",
      created: 0
    });
  });
  availableModels.forEach((item) => {
    const existing = byId.get(item.id);
    byId.set(item.id, {
      id: item.id,
      source: existing?.source || "account",
      priced: Boolean(existing?.priced),
      ownedBy: item.ownedBy,
      created: item.created
    });
  });
  if (defaultModel && !byId.has(defaultModel)) {
    byId.set(defaultModel, {
      id: defaultModel,
      source: "account",
      priced: false,
      ownedBy: "",
      created: 0
    });
  }
  return Array.from(byId.values()).sort((left, right) => left.id.localeCompare(right.id));
}
