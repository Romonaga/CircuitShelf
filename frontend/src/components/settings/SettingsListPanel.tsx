import type { AppSetting } from "../../types";
import type { SettingGroupOption, SettingsGroup } from "../../hooks/useSystemSettings";
import { ErrorMessage } from "../ErrorMessage";
import { SectionHeader } from "../SectionHeader";

export function SettingsListPanel({
  busy,
  error,
  filter,
  groupFilter,
  groupedSettings,
  groups,
  hiddenAdvancedCount,
  selected,
  settingsCount,
  showAdvanced,
  visibleCount,
  onFilterChange,
  onGroupFilterChange,
  onSelectSetting,
  onShowAdvancedChange
}: {
  busy: boolean;
  error: string;
  filter: string;
  groupFilter: string;
  groupedSettings: SettingsGroup[];
  groups: SettingGroupOption[];
  hiddenAdvancedCount: number;
  selected: AppSetting | null;
  settingsCount: number;
  showAdvanced: boolean;
  visibleCount: number;
  onFilterChange: (value: string) => void;
  onGroupFilterChange: (value: string) => void;
  onSelectSetting: (setting: AppSetting) => void;
  onShowAdvancedChange: (value: boolean) => void;
}) {
  return (
    <aside className="settings-list-panel">
      <SectionHeader
        title="Settings"
        description={busy ? "Loading..." : `${visibleCount} visible of ${settingsCount} curated settings`}
      />
      <div className="settings-toolbar">
        <input value={filter} onChange={(event) => onFilterChange(event.target.value)} placeholder="Filter settings" />
        <select value={groupFilter} onChange={(event) => onGroupFilterChange(event.target.value)} aria-label="Setting group">
          <option value="all">All groups</option>
          {groups.map((group) => (
            <option key={group.key} value={group.key}>
              {group.label}
            </option>
          ))}
        </select>
        <label className="inline-check settings-advanced-toggle">
          <input type="checkbox" checked={showAdvanced} onChange={(event) => onShowAdvancedChange(event.target.checked)} />
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
                  onClick={() => onSelectSetting(setting)}
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
  );
}
