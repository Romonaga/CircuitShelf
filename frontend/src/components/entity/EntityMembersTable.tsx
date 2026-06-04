import type { EntityMember } from "../../types";

export function EntityMembersTable({
  disableDrafts,
  members,
  resetDrafts,
  onChangeRole,
  onDisable,
  onDisableDraftChange,
  onEnable,
  onForcePasswordChange,
  onResetDraftChange,
  onResetPassword
}: {
  disableDrafts: Record<number, string>;
  members: EntityMember[];
  resetDrafts: Record<number, string>;
  onChangeRole: (member: EntityMember, role: string) => void;
  onDisable: (member: EntityMember) => void;
  onDisableDraftChange: (userId: number, value: string) => void;
  onEnable: (member: EntityMember) => void;
  onForcePasswordChange: (member: EntityMember) => void;
  onResetDraftChange: (userId: number, value: string) => void;
  onResetPassword: (member: EntityMember) => void;
}) {
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th>User</th>
            <th>Role</th>
            <th>Email</th>
            <th>System</th>
            <th>Status</th>
            <th>Security</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <tr key={member.userId}>
              <td>
                <strong>{member.displayName || member.nickname || member.username}</strong>
                <small>{member.username}</small>
              </td>
              <td>
                <select value={member.role} onChange={(event) => onChangeRole(member, event.target.value)}>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="owner">Owner</option>
                </select>
              </td>
              <td>{member.email || "Not set"}</td>
              <td>{member.canManageSystem ? "System admin" : "No"}</td>
              <td>{member.disabledAt ? "Disabled" : (member.isActive ? "Active" : "Inactive")}</td>
              <td>
                <small>{member.failedLoginCount || 0} failed</small>
                {member.forcePasswordChange ? <small>Password change required</small> : null}
                {member.disabledReason ? <small>{member.disabledReason}</small> : null}
              </td>
              <td>
                <div className="row-actions">
                  {member.disabledAt ? (
                    <button type="button" className="ghost-button" onClick={() => onEnable(member)}>
                      Enable
                    </button>
                  ) : null}
                  {!member.forcePasswordChange ? (
                    <button type="button" className="ghost-button" onClick={() => onForcePasswordChange(member)}>
                      Force reset
                    </button>
                  ) : null}
                  <div className="member-reset-row">
                    <input
                      type="password"
                      value={resetDrafts[member.userId] || ""}
                      onChange={(event) => onResetDraftChange(member.userId, event.target.value)}
                      placeholder="temporary password"
                    />
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={!resetDrafts[member.userId]}
                      onClick={() => onResetPassword(member)}
                    >
                      Reset
                    </button>
                  </div>
                  {!member.disabledAt ? (
                    <div className="member-reset-row">
                      <input
                        value={disableDrafts[member.userId] || ""}
                        onChange={(event) => onDisableDraftChange(member.userId, event.target.value)}
                        placeholder="disable reason"
                      />
                      <button type="button" className="danger-button" onClick={() => onDisable(member)}>
                        Disable
                      </button>
                    </div>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
