import type { AIAvailableModel, AIModelPricing, AIProviderSettings, AIProviderSettingsPayload } from "../types";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { AIProviderPricingOverrides } from "./AIProviderPricingOverrides";
import { useAIProviderSettingsForm } from "../hooks/useAIProviderSettingsForm";
import { AIProviderBudgetFields } from "./aiProvider/AIProviderBudgetFields";
import { AIProviderKeyFields } from "./aiProvider/AIProviderKeyFields";
import { AIProviderMainFields } from "./aiProvider/AIProviderMainFields";
import { AIProviderModelRefresh } from "./aiProvider/AIProviderModelRefresh";
import { AIProviderPricingStrip } from "./aiProvider/AIProviderPricingStrip";

export function AIProviderSettingsPanel({
  title,
  description,
  loadSettings,
  loadModels,
  saveSettings,
  canManage,
  showKeyPolicy = true,
  showBudget = true
}: {
  title: string;
  description: string;
  loadSettings: () => Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>;
  loadModels?: () => Promise<{ models: AIAvailableModel[] }>;
  saveSettings: (payload: AIProviderSettingsPayload) => Promise<{ settings: AIProviderSettings }>;
  canManage: boolean;
  showKeyPolicy?: boolean;
  showBudget?: boolean;
}) {
  const {
    apiKey,
    availableModels,
    busy,
    clearApiKey,
    error,
    message,
    modelOptions,
    pricing,
    refreshingModels,
    saving,
    selectedPrice,
    settings,
    refreshAvailableModels,
    setApiKey,
    setClearApiKey,
    setSettings,
    submit,
  } = useAIProviderSettingsForm({ canManage, loadSettings, loadModels, saveSettings });

  return (
    <form className="ai-provider-panel" onSubmit={submit}>
      <SectionHeader title={title} description={busy ? "Loading..." : description} />
      <ErrorMessage message={error} />

      <AIProviderMainFields
        canManage={canManage}
        modelOptions={modelOptions}
        settings={settings}
        showKeyPolicy={showKeyPolicy}
        onChange={setSettings}
      />
      <AIProviderKeyFields
        apiKey={apiKey}
        canManage={canManage}
        clearApiKey={clearApiKey}
        settings={settings}
        onApiKeyChange={setApiKey}
        onClearApiKeyChange={setClearApiKey}
      />

      {loadModels ? (
        <AIProviderModelRefresh
          canManage={canManage}
          hasApiKey={settings.hasApiKey}
          modelsCount={availableModels.length}
          refreshing={refreshingModels}
          onRefresh={refreshAvailableModels}
        />
      ) : null}

      {showBudget ? <AIProviderBudgetFields canManage={canManage} settings={settings} onChange={setSettings} /> : null}
      <AIProviderPricingStrip price={selectedPrice} />

      <AIProviderPricingOverrides
        pricing={pricing}
        overrides={settings.pricingOverrides || []}
        disabled={!canManage}
        onChange={(pricingOverrides) => setSettings({ ...settings, pricingOverrides })}
      />

      {message ? <p className="success-message">{message}</p> : null}
      {canManage ? (
        <button className="primary-button" disabled={saving || busy}>
          {saving ? "Saving..." : "Save AI settings"}
        </button>
      ) : null}
    </form>
  );
}
