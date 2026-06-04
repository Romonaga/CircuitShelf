import {
  getSystemAIProvider,
  getSystemAIProviderModels,
  getSystemPasswordPolicy,
  updateSystemAIProvider,
  updateSystemPasswordPolicy
} from "../api";
import { useSystemSettings } from "../hooks/useSystemSettings";
import { AIProviderSettingsPanel } from "./AIProviderSettingsPanel";
import { PasswordPolicyPanel } from "./PasswordPolicyPanel";
import { SettingsEditorPanel } from "./settings/SettingsEditorPanel";
import { SettingsListPanel } from "./settings/SettingsListPanel";

export function SettingsView() {
  const settings = useSystemSettings();

  return (
    <section className="view-grid settings-grid">
      <SettingsListPanel
        busy={settings.busy}
        error={settings.error}
        filter={settings.filter}
        groupFilter={settings.groupFilter}
        groupedSettings={settings.groupedSettings}
        groups={settings.groups}
        hiddenAdvancedCount={settings.hiddenAdvancedCount}
        selected={settings.selected}
        settingsCount={settings.settingsCount}
        showAdvanced={settings.showAdvanced}
        visibleCount={settings.visibleCount}
        onFilterChange={settings.setFilter}
        onGroupFilterChange={settings.setGroupFilter}
        onSelectSetting={settings.selectSetting}
        onShowAdvancedChange={settings.setShowAdvanced}
      />

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
        <SettingsEditorPanel
          busy={settings.busy}
          draftValue={settings.draftValue}
          message={settings.message}
          saving={settings.saving}
          selected={settings.selected}
          onDraftValueChange={settings.setDraftValue}
          onLoadSettings={() => void settings.loadSettings()}
          onSubmit={(event) => void settings.submit(event)}
        />
      </div>
    </section>
  );
}
