import type { AIProviderSettings } from "../../types";

export function AIProviderBillingFields({
  canManage,
  settings,
  onChange
}: {
  canManage: boolean;
  settings: AIProviderSettings;
  onChange: (settings: AIProviderSettings) => void;
}) {
  return (
    <div className="ai-provider-grid">
      <label>
        OpenAI project ID
        <input
          value={settings.providerProjectId}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, providerProjectId: event.target.value })}
          placeholder="proj_..."
          autoComplete="off"
        />
      </label>
      <label>
        OpenAI API key ID
        <input
          value={settings.providerApiKeyId}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, providerApiKeyId: event.target.value })}
          placeholder="key_..."
          autoComplete="off"
        />
      </label>
    </div>
  );
}
