import { FormEvent, useEffect, useMemo, useState } from "react";
import type { AIAvailableModel, AIModelPricing, AIProviderSettings, AIProviderSettingsPayload } from "../types";
import { errorMessage } from "../libs/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";
import { AIProviderPricingOverrides } from "./AIProviderPricingOverrides";
import { buildModelOptions } from "../libs/aiProvider/models";
import { AIProviderBudgetFields } from "./aiProvider/AIProviderBudgetFields";
import { AIProviderKeyFields } from "./aiProvider/AIProviderKeyFields";
import { AIProviderMainFields } from "./aiProvider/AIProviderMainFields";
import { AIProviderModelRefresh } from "./aiProvider/AIProviderModelRefresh";
import { AIProviderPricingStrip } from "./aiProvider/AIProviderPricingStrip";

const defaultSettings: AIProviderSettings = {
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
  const [settings, setSettings] = useState<AIProviderSettings>(defaultSettings);
  const [pricing, setPricing] = useState<AIModelPricing[]>([]);
  const [availableModels, setAvailableModels] = useState<AIAvailableModel[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [busy, setBusy] = useState(false);
  const [refreshingModels, setRefreshingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setBusy(true);
    setError("");
    loadSettings()
      .then((response) => {
        if (!active) {
          return;
        }
        const loaded = response.settings;
        const firstActiveModel = response.pricing.find((item) => item.isActive)?.modelName || "";
        setPricing(response.pricing);
        setSettings({
          ...defaultSettings,
          ...loaded,
          defaultModel: loaded.defaultModel || firstActiveModel
        });
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load AI provider settings"));
        }
      })
      .finally(() => {
        if (active) {
          setBusy(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadSettings]);

  const selectedPrice = useMemo(
    () => pricing.find((item) => item.modelName === settings.defaultModel),
    [pricing, settings.defaultModel]
  );

  const modelOptions = useMemo(() => {
    return buildModelOptions({ availableModels, defaultModel: settings.defaultModel, pricing });
  }, [availableModels, pricing, settings.defaultModel]);

  async function refreshAvailableModels() {
    if (!loadModels || !canManage) {
      return;
    }
    setRefreshingModels(true);
    setError("");
    setMessage("");
    try {
      const response = await loadModels();
      setAvailableModels(response.models);
      setMessage(`${response.models.length} OpenAI models available for this key.`);
    } catch (err) {
      setError(errorMessage(err, "Could not refresh OpenAI models"));
    } finally {
      setRefreshingModels(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await saveSettings({
        enabled: settings.enabled,
        apiKey: apiKey.trim() || undefined,
        clearApiKey,
        keyPolicy: settings.keyPolicy,
        assistMode: settings.assistMode,
        defaultModel: settings.defaultModel,
        monthlyBudget: settings.monthlyBudget,
        warnPercent: settings.warnPercent,
        stopPercent: settings.stopPercent,
        pricingOverrides: settings.pricingOverrides
      });
      setSettings(response.settings);
      setApiKey("");
      setClearApiKey(false);
      setMessage("AI provider settings saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save AI provider settings"));
    } finally {
      setSaving(false);
    }
  }

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
