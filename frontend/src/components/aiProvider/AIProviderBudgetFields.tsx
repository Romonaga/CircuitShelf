import type { AIProviderSettings } from "../../types";

export function AIProviderBudgetFields({
  canManage,
  settings,
  onChange
}: {
  canManage: boolean;
  settings: AIProviderSettings;
  onChange: (settings: AIProviderSettings) => void;
}) {
  return (
    <div className="ai-provider-grid compact">
      <label>
        Monthly budget
        <input
          type="number"
          min={0}
          step="0.01"
          value={settings.monthlyBudget}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, monthlyBudget: Number(event.target.value) })}
        />
      </label>
      <label>
        Warn %
        <input
          type="number"
          min={1}
          max={100}
          value={settings.warnPercent}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, warnPercent: Number(event.target.value) })}
        />
      </label>
      <label>
        Stop %
        <input
          type="number"
          min={1}
          max={100}
          value={settings.stopPercent}
          disabled={!canManage}
          onChange={(event) => onChange({ ...settings, stopPercent: Number(event.target.value) })}
        />
      </label>
    </div>
  );
}
