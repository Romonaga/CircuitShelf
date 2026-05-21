import { FormEvent, useEffect, useMemo, useState } from "react";
import { getSettings, updateSetting } from "../api";
import type { AppSetting, SettingValue } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function SettingsView() {
  const [settings, setSettings] = useState<AppSetting[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [draftValue, setDraftValue] = useState<SettingValue>("");
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const filteredSettings = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    if (!needle) {
      return settings;
    }
    return settings.filter((setting) => `${setting.key} ${setting.description}`.toLowerCase().includes(needle));
  }, [filter, settings]);

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
      const nextSelected = response.settings.find((setting) => setting.key === selectedKey) || response.settings[0];
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

  return (
    <section className="view-grid settings-grid">
      <aside className="settings-list-panel">
        <SectionHeader title="Settings" description={busy ? "Loading..." : `${settings.length} editable values`} />
        <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter settings" />
        <ErrorMessage message={error} />
        <div className="settings-list">
          {filteredSettings.map((setting) => (
            <button
              key={setting.key}
              className={setting.key === selected?.key ? "settings-row active" : "settings-row"}
              onClick={() => selectSetting(setting)}
            >
              <span>{setting.key}</span>
              <small>{setting.valueType}</small>
            </button>
          ))}
        </div>
      </aside>

      <form className="settings-editor-panel" onSubmit={submit}>
        <SectionHeader
          title={selected?.key || "No setting selected"}
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
              <span>Type: {selected.valueType}</span>
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
