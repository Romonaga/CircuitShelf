import type { EntityMember } from "../../types";
import { ErrorMessage } from "../ErrorMessage";
import { SectionHeader } from "../SectionHeader";
import { EntityMemberCreateForm } from "./EntityMemberCreateForm";
import { EntityMembersTable } from "./EntityMembersTable";
import type { NewEntityMemberDraft } from "../../hooks/useEntityMembers";

export function EntityMembersPanel({
  busy,
  disableDrafts,
  error,
  members,
  message,
  newMember,
  resetDrafts,
  onChangeRole,
  onCreate,
  onDisable,
  onDisableDraftChange,
  onEnable,
  onForcePasswordChange,
  onLoadMembers,
  onNewMemberChange,
  onResetDraftChange,
  onResetPassword
}: {
  busy: boolean;
  disableDrafts: Record<number, string>;
  error: string;
  members: EntityMember[];
  message: string;
  newMember: NewEntityMemberDraft;
  resetDrafts: Record<number, string>;
  onChangeRole: (member: EntityMember, role: string) => void;
  onCreate: () => void;
  onDisable: (member: EntityMember) => void;
  onDisableDraftChange: (userId: number, value: string) => void;
  onEnable: (member: EntityMember) => void;
  onForcePasswordChange: (member: EntityMember) => void;
  onLoadMembers: () => void;
  onNewMemberChange: (draft: NewEntityMemberDraft) => void;
  onResetDraftChange: (userId: number, value: string) => void;
  onResetPassword: (member: EntityMember) => void;
}) {
  return (
    <div className="members-panel">
      <SectionHeader
        title="Members"
        description={busy ? "Loading..." : `${members.length} active members`}
        actions={
          <button className="ghost-button" onClick={onLoadMembers}>
            Refresh
          </button>
        }
      />
      <ErrorMessage message={error} />
      {message ? <p className="success-message">{message}</p> : null}
      <EntityMemberCreateForm draft={newMember} onChange={onNewMemberChange} onCreate={onCreate} />
      <EntityMembersTable
        disableDrafts={disableDrafts}
        members={members}
        resetDrafts={resetDrafts}
        onChangeRole={onChangeRole}
        onDisable={onDisable}
        onDisableDraftChange={onDisableDraftChange}
        onEnable={onEnable}
        onForcePasswordChange={onForcePasswordChange}
        onResetDraftChange={onResetDraftChange}
        onResetPassword={onResetPassword}
      />
    </div>
  );
}
