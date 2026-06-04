import {
  getEntityAIProvider,
  getEntityAIProviderModels,
  getEntityPasswordPolicy,
  updateEntityAIProvider,
  updateEntityPasswordPolicy
} from "../api";
import { useEntityMembers } from "../hooks/useEntityMembers";
import type { EntityContext } from "../types";
import { AIProviderSettingsPanel } from "./AIProviderSettingsPanel";
import { EntityHero } from "./entity/EntityHero";
import { EntityMembersPanel } from "./entity/EntityMembersPanel";
import { PasswordPolicyPanel } from "./PasswordPolicyPanel";

export function EntitySettingsView({
  entity,
  canManage
}: {
  entity?: EntityContext | null;
  canManage: boolean;
}) {
  const members = useEntityMembers(canManage);

  if (!entity) {
    return <div className="empty-state">No entity membership is configured for this account.</div>;
  }

  return (
    <section className="entity-view">
      <EntityHero entity={entity} canManage={canManage} />

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
        <EntityMembersPanel
          busy={members.busy}
          disableDrafts={members.disableDrafts}
          error={members.error}
          members={members.members}
          message={members.message}
          newMember={members.newMember}
          resetDrafts={members.resetDrafts}
          onChangeRole={(member, role) => void members.changeRole(member, role)}
          onCreate={() => void members.createMember()}
          onDisable={(member) => void members.disableMember(member)}
          onDisableDraftChange={(userId, value) => members.setDisableDrafts((current) => ({ ...current, [userId]: value }))}
          onEnable={(member) => void members.enableMember(member)}
          onForcePasswordChange={members.forcePasswordChange}
          onLoadMembers={members.loadMembers}
          onNewMemberChange={members.setNewMember}
          onResetDraftChange={(userId, value) => members.setResetDrafts((current) => ({ ...current, [userId]: value }))}
          onResetPassword={(member) => void members.resetPassword(member)}
        />
      ) : null}
    </section>
  );
}
