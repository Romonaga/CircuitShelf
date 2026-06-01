import type { AppConfig, QueryOptions } from "../types";

export const ASK_RETRIEVAL_PREFERENCE_KEY = "ask.retrieval";

export interface AskRetrievalPreference {
  model?: string;
  strategy?: string;
  topK?: number;
  distanceThreshold?: number;
  maxTokens?: number;
  showFullText?: boolean;
  bypassCache?: boolean;
}

export interface ResolvedAskPreferences {
  model: string;
  options: QueryOptions;
}

function numberInRange(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, parsed));
}

export function resolveAskPreferences(config: AppConfig, preference?: Partial<AskRetrievalPreference> | null): ResolvedAskPreferences {
  const strategy =
    preference?.strategy && config.retrievalStrategies.includes(preference.strategy)
      ? preference.strategy
      : config.defaults.strategy;
  const model =
    preference?.model && config.models.includes(preference.model)
      ? preference.model
      : config.defaultModel;

  return {
    model,
    options: {
      strategy,
      topK: numberInRange(preference?.topK, config.defaults.topK, 1, 80),
      distanceThreshold: numberInRange(preference?.distanceThreshold, config.defaults.distanceThreshold, 0.1, 100),
      maxTokens: numberInRange(preference?.maxTokens, config.defaults.maxTokens, 100, 100000),
      showFullText: typeof preference?.showFullText === "boolean" ? preference.showFullText : config.defaults.showFullText,
      bypassCache: typeof preference?.bypassCache === "boolean" ? preference.bypassCache : config.defaults.bypassCache,
    },
  };
}

export function preferenceFromResolved(model: string, options: QueryOptions): AskRetrievalPreference {
  return {
    model,
    strategy: options.strategy,
    topK: options.topK,
    distanceThreshold: options.distanceThreshold,
    maxTokens: options.maxTokens,
    showFullText: options.showFullText,
    bypassCache: options.bypassCache,
  };
}
