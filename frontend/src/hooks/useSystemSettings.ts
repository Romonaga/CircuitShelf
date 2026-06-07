import { FormEvent, useEffect, useMemo, useState } from "react";
import { getSettings, updateSetting } from "../libs/api";
import { errorMessage } from "../libs/errors";
import type { AppSetting, SettingValue } from "../types";

export interface SettingsGroup {
  key: string;
  label: string;
  description: string;
  settings: AppSetting[];
}

export interface SettingGroupOption {
  key: string;
  label: string;
  description: string;
}

export function useSystemSettings() {
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

  const groups = useMemo<SettingGroupOption[]>(() => {
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
      if (response.change.restartRequired) {
        setMessage(`${selected.key} saved. Restart required before it is active.`);
      } else if (response.change.runtimeApplied) {
        setMessage(`${selected.key} saved and applied to new work.`);
      } else {
        setMessage(`${selected.key} saved.`);
      }
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

  useEffect(() => {
    void loadSettings();
  }, []);

  return {
    busy,
    draftValue,
    error,
    filter,
    groupFilter,
    groupedSettings,
    groups,
    hiddenAdvancedCount: settings.filter((setting) => setting.advanced).length,
    loadSettings,
    message,
    saving,
    selected,
    setDraftValue,
    setFilter,
    setGroupFilter,
    setShowAdvanced,
    settingsCount: settings.length,
    showAdvanced,
    submit,
    visibleCount: filteredSettings.length,
    selectSetting
  };
}
