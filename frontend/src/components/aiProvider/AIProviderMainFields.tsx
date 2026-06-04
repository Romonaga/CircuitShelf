import type { AIProviderSettings } from "../../types";
import type { AIModelOption } from "../../libs/aiProvider/models";

export function AIProviderMainFields({
  canManage,
  modelOptions,
  settings,
  showKeyPolicy,
  onChange
}: {
  canManage: boolean;
  modelOptions: AIModelOption[];
  settings: AIProviderSettings;
  showKeyPolicy: boolean;
  onChange: (settings: AIProviderSettings) => void;
}) {
  return (
    <div className="ai-provider-grid">
      <label className="inline-check ai-provider-enabled">
        <input
          type="checkbox"
          checked={settings.enabled}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, enabled: event.target.checked })}
        />
        Enable OpenAI assist
      </label>
      <label>
        Assist mode
        <select
          value={settings.assistMode}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, assistMode: event.target.value })}
        >
          <option value="auto">Auto</option>
          <option value="always">Always</option>
          <option value="off">Off</option>
        </select>
      </label>
      {showKeyPolicy ? (
        <label>
          Key policy
          <select
            value={settings.keyPolicy}
            disabled={!canManage}
            onChange={(event) => onChange({ ...settings, keyPolicy: event.target.value })}
          >
            <option value="entity">Entity key</option>
            <option value="user_when_available">User key when available</option>
            <option value="user_only">User key only</option>
            <option value="system">System key</option>
          </select>
        </label>
      ) : null}
      <label>
        Default model
        <select
          value={settings.defaultModel}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, defaultModel: event.target.value })}
        >
          <option value="">Select a model</option>
          {modelOptions.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id}{item.priced ? "" : " (unpriced)"}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
