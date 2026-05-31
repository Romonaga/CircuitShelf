import { useCallback, useEffect, useState } from "react";
import {
  forceEntityMemberPasswordChange,
  getEntityAIProvider,
  getEntityMembers,
  getEntityPasswordPolicy,
  unlockEntityMember,
  updateEntityAIProvider,
  updateEntityPasswordPolicy
} from "../api";
import type { EntityContext, EntityMember } from "../types";
import { errorMessage } from "../lib/errors";
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
                    <td>{member.roleName}</td>
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
                            onClick={() => void runMemberAction(
                              () => unlockEntityMember(member.userId),
                              `${member.username} was unlocked.`
                            )}
                          >
                            Unlock
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
