import { useCallback, useEffect, useState } from "react";
import { getEntityMembers, getEntityPasswordPolicy, updateEntityPasswordPolicy } from "../api";
import type { EntityContext, EntityMember } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";
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
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Email</th>
                  <th>System</th>
                  <th>Status</th>
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
                    <td>{member.isActive ? "Active" : "Inactive"}</td>
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
