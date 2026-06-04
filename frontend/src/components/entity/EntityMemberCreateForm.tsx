import type { NewEntityMemberDraft } from "../../hooks/useEntityMembers";

export function EntityMemberCreateForm({
  draft,
  onChange,
  onCreate
}: {
  draft: NewEntityMemberDraft;
  onChange: (draft: NewEntityMemberDraft) => void;
  onCreate: () => void;
}) {
  return (
    <div className="member-create-panel">
      <label>
        Username
        <input value={draft.username} onChange={(event) => onChange({ ...draft, username: event.target.value })} placeholder="new-user" />
      </label>
      <label>
        Temporary password
        <input
          type="password"
          value={draft.temporaryPassword}
          onChange={(event) => onChange({ ...draft, temporaryPassword: event.target.value })}
          placeholder="Force change on login"
        />
      </label>
      <label>
        Email
        <input value={draft.email} onChange={(event) => onChange({ ...draft, email: event.target.value })} placeholder="optional" />
      </label>
      <label>
        Display name
        <input value={draft.displayName} onChange={(event) => onChange({ ...draft, displayName: event.target.value })} placeholder="optional" />
      </label>
      <label>
        Role
        <select value={draft.role} onChange={(event) => onChange({ ...draft, role: event.target.value })}>
          <option value="user">User</option>
          <option value="admin">Admin</option>
          <option value="owner">Owner</option>
        </select>
      </label>
      <label className="inline-check">
        <input
          type="checkbox"
          checked={draft.forcePasswordChange}
          onChange={(event) => onChange({ ...draft, forcePasswordChange: event.target.checked })}
        />
        Force change
      </label>
      <button className="primary-button" type="button" disabled={!draft.username || !draft.temporaryPassword} onClick={onCreate}>
        Create member
      </button>
    </div>
  );
}
