import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  getSettings,
  getSystemAIProvider,
  getSystemAIProviderModels,
  getSystemPasswordPolicy,
  updateSetting,
  updateSystemAIProvider,
  updateSystemPasswordPolicy
} from "../api";
import type { AppSetting, SettingValue } from "../types";
import { errorMessage } from "../libs/errors";
import { ErrorMessage } from "./ErrorMessage";
import { AIProviderSettingsPanel } from "./AIProviderSettingsPanel";
import { PasswordPolicyPanel } from "./PasswordPolicyPanel";
import { SectionHeader } from "./SectionHeader";

interface SettingsGroup {
  key: string;
  label: string;
  description: string;
  settings: AppSetting[];
}

export function SettingsView() {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [draftValue, setDraftValue] = useState<SettingValue>("");
  const [filter, setFilter] = useState("");
  const [groupFilter, setGroupFilter] = useState("all");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const groups = useMemo(() => {
    const seen = new Map<string, { label: string; description: string }>();
    settings.forEach((setting) => {
      if (!seen.has(setting.group)) {
        seen.set(setting.group, {
          label: setting.groupLabel,
          description: setting.groupDescription || ""
        });
      }
    });
    return Array.from(seen, ([key, group]) => ({ key, ...group }));
  }, [settings]);

  const filteredSettings = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return settings.filter((setting) => {
      if (!showAdvanced && setting.advanced) {
        return false;
      }
      if (groupFilter !== "all" && setting.group !== groupFilter) {
        return false;
      }
      if (!needle) {
        return true;
      }
      return `${setting.key} ${setting.label} ${setting.description} ${setting.groupLabel}`.toLowerCase().includes(needle);
    });
  }, [filter, groupFilter, settings, showAdvanced]);

  const groupedSettings = useMemo<SettingsGroup[]>(() => {
    const byGroup = new Map<string, SettingsGroup>();
    filteredSettings.forEach((setting) => {
      if (!byGroup.has(setting.group)) {
        byGroup.set(setting.group, {
          key: setting.group,
          label: setting.groupLabel,
          description: setting.groupDescription || "",
          settings: []
        });
      }
      byGroup.get(setting.group)?.settings.push(setting);
    });
    return Array.from(byGroup.values());
  }, [filteredSettings]);

  const selected = useMemo(() => settings.find((setting) => setting.key === selectedKey) || null, [selectedKey, settings]);

  useEffect(() => {
    void loadSettings();
  }, []);

  async function loadSettings() {
    setBusy(true);
    setError("");
    try {
      const response = await getSettings();
      setSettings(response.settings);
      const nextSelected =
        response.settings.find((setting) => setting.key === selectedKey) ||
        response.settings.find((setting) => !setting.advanced) ||
        response.settings[0];
      if (nextSelected) {
        selectSetting(nextSelected);
      }
    } catch (err) {
      setError(errorMessage(err, "Could not load settings"));
    } finally {
      setBusy(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!selected) {
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await updateSetting(selected.key, draftValue);
      setSettings((items) => items.map((item) => (item.key === response.setting.key ? response.setting : item)));
      setDraftValue(response.setting.value);
      setMessage(`${selected.key} saved.`);
    } catch (err) {
      setError(errorMessage(err, "Could not save setting"));
    } finally {
      setSaving(false);
    }
  }

  function selectSetting(setting: AppSetting) {
    setSelectedKey(setting.key);
    setDraftValue(setting.value);
    setMessage("");
  }

  const visibleCount = filteredSettings.length;
  const hiddenAdvancedCount = settings.filter((setting) => setting.advanced).length;

  return (
    <section className="view-grid settings-grid">
      <aside className="settings-list-panel">
        <SectionHeader
          title="Settings"
          description={busy ? "Loading..." : `${visibleCount} visible of ${settings.length} curated settings`}
        />
        <div className="settings-toolbar">
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter settings" />
          <select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)} aria-label="Setting group">
            <option value="all">All groups</option>
            {groups.map((group) => (
              <option key={group.key} value={group.key}>
                {group.label}
              </option>
            ))}
          </select>
          <label className="inline-check settings-advanced-toggle">
            <input type="checkbox" checked={showAdvanced} onChange={(event) => setShowAdvanced(event.target.checked)} />
            Show advanced
          </label>
          {!showAdvanced && hiddenAdvancedCount ? (
            <p className="settings-hint">{hiddenAdvancedCount} lower-level settings hidden.</p>
          ) : null}
        </div>
        <ErrorMessage message={error} />
        <div className="settings-list">
          {groupedSettings.length ? (
            groupedSettings.map((group) => (
              <div className="settings-group" key={group.key}>
                <div className="settings-group-heading">
                  <strong>{group.label}</strong>
                  <small>{group.description}</small>
                </div>
                {group.settings.map((setting) => (
                  <button
                    key={setting.key}
                    className={setting.key === selected?.key ? "settings-row active" : "settings-row"}
                    onClick={() => selectSetting(setting)}
                  >
                    <span>{setting.label}</span>
                    <small>{setting.key}</small>
                    <div className="setting-row-tags">
                      <em>{setting.valueType}</em>
                      {setting.advanced ? <em>advanced</em> : null}
                    </div>
                  </button>
                ))}
              </div>
            ))
          ) : (
            <div className="empty-state compact">No settings match the current filters.</div>
          )}
        </div>
      </aside>

      <div className="settings-editor-stack">
        <PasswordPolicyPanel
          title="System password policy"
          description="Default account rules used when an entity has not set its own policy."
          loadPolicy={getSystemPasswordPolicy}
          savePolicy={updateSystemPasswordPolicy}
          canManage
        />
        <AIProviderSettingsPanel
          title="System OpenAI key"
          description="System-paid AI assist configuration for global corpus and operator workflows."
          loadSettings={getSystemAIProvider}
          loadModels={getSystemAIProviderModels}
          saveSettings={updateSystemAIProvider}
          canManage
          showKeyPolicy={false}
          showBudget={false}
        />
        <form className="settings-editor-panel" onSubmit={submit}>
          <SectionHeader
            title={selected?.label || "No setting selected"}
            description={selected?.restartRequired ? "Saved changes are stored in Postgres and applied on next restart." : ""}
            actions={
              <button className="ghost-button" type="button" onClick={loadSettings} disabled={busy || saving}>
                Refresh
              </button>
            }
          />
          {selected ? (
            <>
              <label>
                Value
                <SettingInput setting={selected} value={draftValue} onChange={setDraftValue} />
              </label>
              <div className="setting-meta">
                <span>Key: {selected.key}</span>
                <span>Group: {selected.groupLabel}</span>
                <span>Type: {selected.valueType}</span>
                {selected.advanced ? <span>Advanced</span> : null}
                {selected.updatedAt ? <span>Updated: {new Date(selected.updatedAt).toLocaleString()}</span> : null}
              </div>
              {selected.description ? <p className="setting-description">{selected.description}</p> : null}
              {message ? <p className="success-message">{message}</p> : null}
              <button className="primary-button" disabled={saving}>
                {saving ? "Saving..." : "Save setting"}
              </button>
            </>
          ) : (
            <div className="empty-state">No editable settings found.</div>
          )}
        </form>
      </div>
    </section>
  );
}

function SettingInput({
  setting,
  value,
  onChange
}: {
  setting: AppSetting;
  value: SettingValue;
  onChange: (value: SettingValue) => void;
}) {
  if (setting.valueType === "boolean") {
    return (
      <select value={String(value)} onChange={(event) => onChange(event.target.value === "true")}>
        <option value="true">true</option>
        <option value="false">false</option>
      </select>
    );
  }

  if (setting.valueType === "integer" || setting.valueType === "numeric") {
    return (
      <input
        type="number"
        step={setting.valueType === "integer" ? "1" : "any"}
        value={String(value)}
        onChange={(event) => onChange(setting.valueType === "integer" ? Number.parseInt(event.target.value || "0", 10) : Number(event.target.value))}
      />
    );
  }

  const stringValue = String(value ?? "");
  if (stringValue.length > 120 || stringValue.includes("\n")) {
    return <textarea rows={10} value={stringValue} onChange={(event) => onChange(event.target.value)} />;
  }
  return <input value={stringValue} onChange={(event) => onChange(event.target.value)} />;
}
