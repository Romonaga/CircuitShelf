export type SettingValueType = "text" | "integer" | "numeric" | "boolean";
export type SettingValue = string | number | boolean;

export interface AppSetting {
  key: string;
  label: string;
  group: string;
  groupLabel: string;
  groupDescription?: string;
  value: SettingValue;
  valueType: SettingValueType;
  description: string;
  rawDescription?: string;
  advanced: boolean;
  updatedAt?: string | null;
  restartRequired: boolean;
}

export interface RuntimeLlmModel {
  id: number;
  modelName: string;
  displayName: string;
  provider: string;
  isDefault: boolean;
  isEnabled: boolean;
  temperature: number;
  numPredict: number;
  numCtx?: number | null;
  updatedAt?: string | null;
}

export interface RuntimeRerankProfile {
  id: number;
  name: string;
  weightVector: number;
  weightRerank: number;
  isDefault: boolean;
  keywords: string[];
  updatedAt?: string | null;
}

export interface RuntimeEquationPattern {
  id: number;
  patternType: string;
  pattern: string;
  isRegex: boolean;
  createdAt?: string | null;
}

export interface RuntimeCatalog {
  llmModels: RuntimeLlmModel[];
  rerankProfiles: RuntimeRerankProfile[];
  equationPatterns: RuntimeEquationPattern[];
}
