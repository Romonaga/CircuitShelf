import { useCallback, useEffect, useState } from "react";
import {
  createEntityMember,
  disableEntityMember,
  enableEntityMember,
  forceEntityMemberPasswordChange,
  getEntityAIProvider,
  getEntityAIProviderModels,
  getEntityMembers,
  getEntityPasswordPolicy,
  resetEntityMemberPassword,
  updateEntityMemberRole,
  updateEntityAIProvider,
  updateEntityPasswordPolicy
} from "../api";
import type { EntityContext, EntityMember } from "../types";
import { errorMessage } from "../libs/errors";
import { ErrorMessage } from "./ErrorMessage";
import { AIProviderSettingsPanel } from "./AIProviderSettingsPanel";
import { PasswordPolicyPanel } from "./PasswordPolicyPanel";
import { SectionHeader } from "./SectionHeader";

export function EntitySettingsView({
  entity,
  canManage
}: {
  entity?: EntityContext | null;
  canManage: boolean;
}) {
  const [members, setMembers] = useState<EntityMember[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [newMember, setNewMember] = useState({
    username: "",
    temporaryPassword: "",
    email: "",
    displayName: "",
    role: "user",
    forcePasswordChange: true
  });
  const [resetDrafts, setResetDrafts] = useState<Record<number, string>>({});
  const [disableDrafts, setDisableDrafts] = useState<Record<number, string>>({});

  const loadMembers = useCallback(() => {
    if (!canManage) {
      setMembers([]);
      return;
    }
    setBusy(true);
    setError("");
    getEntityMembers()
      .then((response) => setMembers(response.members))
      .catch((err) => setError(errorMessage(err, "Could not load entity members")))
      .finally(() => setBusy(false));
  }, [canManage]);

  async function runMemberAction(action: () => Promise<{ ok: boolean }>, successMessage: string) {
    setError("");
    setMessage("");
    try {
      await action();
      setMessage(successMessage);
      loadMembers();
    } catch (err) {
      setError(errorMessage(err, "Could not update member"));
    }
  }

  async function disableMember(member: EntityMember) {
    setError("");
    setMessage("");
    try {
      const response = await disableEntityMember(
        member.userId,
        disableDrafts[member.userId] || "Disabled by entity administrator."
      );
      setMembers(response.members);
      setDisableDrafts((current) => ({ ...current, [member.userId]: "" }));
      setMessage(`${member.username} disabled.`);
    } catch (err) {
      setError(errorMessage(err, "Could not disable member"));
    }
  }

  async function enableMember(member: EntityMember) {
    setError("");
    setMessage("");
    try {
      const response = await enableEntityMember(member.userId);
      setMembers(response.members);
      setMessage(`${member.username} enabled.`);
    } catch (err) {
      setError(errorMessage(err, "Could not enable member"));
    }
  }

  async function createMember() {
    setError("");
    setMessage("");
    try {
      const response = await createEntityMember(newMember);
      setMembers(response.members);
      setNewMember({
        username: "",
        temporaryPassword: "",
        email: "",
        displayName: "",
        role: "user",
        forcePasswordChange: true
      });
      setMessage("Entity member created.");
    } catch (err) {
      setError(errorMessage(err, "Could not create member"));
    }
  }

  async function changeRole(member: EntityMember, role: string) {
    setError("");
    setMessage("");
    try {
      const response = await updateEntityMemberRole(member.userId, role);
      setMembers(response.members);
      setMessage(`${member.username} role updated.`);
    } catch (err) {
      setError(errorMessage(err, "Could not update member role"));
    }
  }

  async function resetPassword(member: EntityMember) {
    const temporaryPassword = resetDrafts[member.userId] || "";
    setError("");
    setMessage("");
    try {
      const response = await resetEntityMemberPassword(member.userId, {
        temporaryPassword,
        forcePasswordChange: true
      });
      setMembers(response.members);
      setResetDrafts((current) => ({ ...current, [member.userId]: "" }));
      setMessage(`${member.username} password reset.`);
    } catch (err) {
      setError(errorMessage(err, "Could not reset member password"));
    }
  }

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  if (!entity) {
    return <div className="empty-state">No entity membership is configured for this account.</div>;
  }

  return (
    <section className="entity-view">
      <div className="entity-hero">
        <SectionHeader title={entity.name} description={`${entity.roleName} access`} />
        <div className="entity-stat-row">
          <span>Slug: {entity.slug}</span>
          <span>{canManage ? "Entity management enabled" : "Read-only membership"}</span>
        </div>
      </div>

      <PasswordPolicyPanel
        title="Password policy"
        description="Entity-level rules override the system default for this workspace."
        loadPolicy={getEntityPasswordPolicy}
        savePolicy={updateEntityPasswordPolicy}
        canManage={canManage}
      />

      {canManage ? (
        <AIProviderSettingsPanel
          title="Entity OpenAI key"
          description="Entity-paid AI assist configuration for shared workflows inside this workspace."
          loadSettings={getEntityAIProvider}
          loadModels={getEntityAIProviderModels}
          saveSettings={updateEntityAIProvider}
          canManage={canManage}
          showBudget
        />
      ) : null}

      {canManage ? (
        <div className="members-panel">
          <SectionHeader
            title="Members"
            description={busy ? "Loading..." : `${members.length} active members`}
            actions={
              <button className="ghost-button" onClick={loadMembers}>
                Refresh
              </button>
            }
          />
          <ErrorMessage message={error} />
          {message ? <p className="success-message">{message}</p> : null}
          <div className="member-create-panel">
            <label>
              Username
              <input
                value={newMember.username}
                onChange={(event) => setNewMember({ ...newMember, username: event.target.value })}
                placeholder="new-user"
              />
            </label>
            <label>
              Temporary password
              <input
                type="password"
                value={newMember.temporaryPassword}
                onChange={(event) => setNewMember({ ...newMember, temporaryPassword: event.target.value })}
                placeholder="Force change on login"
              />
            </label>
            <label>
              Email
              <input
                value={newMember.email}
                onChange={(event) => setNewMember({ ...newMember, email: event.target.value })}
                placeholder="optional"
              />
            </label>
            <label>
              Display name
              <input
                value={newMember.displayName}
                onChange={(event) => setNewMember({ ...newMember, displayName: event.target.value })}
                placeholder="optional"
              />
            </label>
            <label>
              Role
              <select value={newMember.role} onChange={(event) => setNewMember({ ...newMember, role: event.target.value })}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
                <option value="owner">Owner</option>
              </select>
            </label>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={newMember.forcePasswordChange}
                onChange={(event) => setNewMember({ ...newMember, forcePasswordChange: event.target.checked })}
              />
              Force change
            </label>
            <button className="primary-button" type="button" disabled={!newMember.username || !newMember.temporaryPassword} onClick={() => void createMember()}>
              Create member
            </button>
          </div>
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
                      <select value={member.role} onChange={(event) => void changeRole(member, event.target.value)}>
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
                          <button
                            type="button"
                            className="ghost-button"
                            onClick={() => void enableMember(member)}
                          >
                            Enable
                          </button>
                        ) : null}
                        {!member.forcePasswordChange ? (
                          <button
                            type="button"
                            className="ghost-button"
                            onClick={() => void runMemberAction(
                              () => forceEntityMemberPasswordChange(member.userId),
                              `${member.username} must change password next login.`
                            )}
                          >
                            Force reset
                          </button>
                        ) : null}
                        <div className="member-reset-row">
                          <input
                            type="password"
                            value={resetDrafts[member.userId] || ""}
                            onChange={(event) => setResetDrafts((current) => ({ ...current, [member.userId]: event.target.value }))}
                            placeholder="temporary password"
                          />
                          <button
                            type="button"
                            className="ghost-button"
                            disabled={!resetDrafts[member.userId]}
                            onClick={() => void resetPassword(member)}
                          >
                            Reset
                          </button>
                        </div>
                        {!member.disabledAt ? (
                          <div className="member-reset-row">
                            <input
                              value={disableDrafts[member.userId] || ""}
                              onChange={(event) => setDisableDrafts((current) => ({ ...current, [member.userId]: event.target.value }))}
                              placeholder="disable reason"
                            />
                            <button
                              type="button"
                              className="danger-button"
                              onClick={() => void disableMember(member)}
                            >
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
        </div>
      ) : null}
    </section>
  );
}
