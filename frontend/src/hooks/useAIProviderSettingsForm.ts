import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";
import type { AIAvailableModel, AIModelPricing, AIProviderSettings, AIProviderSettingsPayload } from "../types";
import { buildModelOptions } from "../libs/aiProvider/models";
import { defaultAIProviderSettings } from "../libs/aiProvider/defaultSettings";
import { errorMessage } from "../libs/errors";

export function useAIProviderSettingsForm({
  canManage,
  loadSettings,
  loadModels,
  saveSettings
}: {
  canManage: boolean;
  loadSettings: () => Promise<{ settings: AIProviderSettings; pricing: AIModelPricing[] }>;
  loadModels?: () => Promise<{ models: AIAvailableModel[] }>;
  saveSettings: (payload: AIProviderSettingsPayload) => Promise<{ settings: AIProviderSettings }>;
}) {
  const [settings, setSettings] = useState<AIProviderSettings>(defaultAIProviderSettings);
  const [pricing, setPricing] = useState<AIModelPricing[]>([]);
  const [availableModels, setAvailableModels] = useState<AIAvailableModel[]>([]);
  const [apiKey, setApiKey] = useState("");
  const [clearApiKey, setClearApiKey] = useState(false);
  const [adminApiKey, setAdminApiKey] = useState("");
  const [clearAdminApiKey, setClearAdminApiKey] = useState(false);
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
          ...defaultAIProviderSettings,
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
        adminApiKey: adminApiKey.trim() || undefined,
        clearAdminApiKey,
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
      setAdminApiKey("");
      setClearAdminApiKey(false);
      setMessage("AI provider settings saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save AI provider settings"));
    } finally {
      setSaving(false);
    }
  }

  return {
    adminApiKey,
    apiKey,
    availableModels,
    busy,
    clearAdminApiKey,
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
    setAdminApiKey,
    setApiKey,
    setClearAdminApiKey,
    setClearApiKey,
    setSettings,
    submit,
  };
}
