import { FormEvent, useEffect, useMemo, useState } from "react";
import { getSettings, updateSetting } from "../libs/api";
import { errorMessage } from "../libs/errors";
import type { AppSetting, SettingValue } from "../types";

const PADDLEOCR_SETTING_KEYS = new Set([
  "PADDLEOCR_LANG",
  "PADDLEOCR_ENGINE",
  "PADDLEOCR_PYTHON",
  "PADDLEOCR_TIMEOUT_SECONDS"
]);

const HIDDEN_OCR_INTERNAL_SETTING_KEYS = new Set([
  "OCR_ENGINE_FALLBACK",
  "PADDLEOCR_DEVICE"
]);

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

  const settingsByKey = useMemo(() => new Map(settings.map((setting) => [setting.key, setting])), [settings]);

  const filteredSettings = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return settings.filter((setting) => {
      if (HIDDEN_OCR_INTERNAL_SETTING_KEYS.has(setting.key)) {
        return false;
      }
      if (!settingVisibleInContext(setting, settingsByKey)) {
        return false;
      }
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
  }, [filter, groupFilter, settings, settingsByKey, showAdvanced]);

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

function settingVisibleInContext(setting: AppSetting, settingsByKey: Map<string, AppSetting>) {
  if (!PADDLEOCR_SETTING_KEYS.has(setting.key)) {
    return true;
  }
  const engine = String(settingsByKey.get("OCR_ENGINE")?.value ?? "").trim().toLowerCase();
  return engine === "paddleocr";
}
