import type { FormEvent } from "react";
import type { AppSetting, SettingValue } from "../../types";
import { SectionHeader } from "../SectionHeader";
import { SettingInput } from "./SettingInput";

export function SettingsEditorPanel({
  busy,
  draftValue,
  message,
  saving,
  selected,
  onDraftValueChange,
  onLoadSettings,
  onSubmit
}: {
  busy: boolean;
  draftValue: SettingValue;
  message: string;
  saving: boolean;
  selected: AppSetting | null;
  onDraftValueChange: (value: SettingValue) => void;
  onLoadSettings: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <form className="settings-editor-panel" onSubmit={onSubmit}>
      <SectionHeader
        title={selected?.label || "No setting selected"}
        description={
          selected?.restartRequired
            ? "Saved changes are stored in Postgres and applied on next restart."
            : selected
              ? "Saved changes are applied to new work without restarting the server."
              : ""
        }
        actions={
          <button className="ghost-button" type="button" onClick={onLoadSettings} disabled={busy || saving}>
            Refresh
          </button>
        }
      />
      {selected ? (
        <>
          <label>
            Value
            <SettingInput setting={selected} value={draftValue} onChange={onDraftValueChange} />
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
  );
}
