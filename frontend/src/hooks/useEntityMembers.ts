import { useCallback, useEffect, useState } from "react";
import {
  createEntityMember,
  disableEntityMember,
  enableEntityMember,
  forceEntityMemberPasswordChange,
  getEntityMembers,
  resetEntityMemberPassword,
  updateEntityMemberRole
} from "../api";
import type { EntityMember } from "../types";
import { errorMessage } from "../libs/errors";

export interface NewEntityMemberDraft {
  username: string;
  temporaryPassword: string;
  email: string;
  displayName: string;
  role: string;
  forcePasswordChange: boolean;
}

export const emptyMemberDraft: NewEntityMemberDraft = {
  username: "",
  temporaryPassword: "",
  email: "",
  displayName: "",
  role: "user",
  forcePasswordChange: true
};

export function useEntityMembers(canManage: boolean) {
  const [members, setMembers] = useState<EntityMember[]>([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [newMember, setNewMember] = useState<NewEntityMemberDraft>(emptyMemberDraft);
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
      setNewMember(emptyMemberDraft);
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

  function forcePasswordChange(member: EntityMember) {
    void runMemberAction(
      () => forceEntityMemberPasswordChange(member.userId),
      `${member.username} must change password next login.`
    );
  }

  useEffect(() => {
    loadMembers();
  }, [loadMembers]);

  return {
    busy,
    changeRole,
    createMember,
    disableDrafts,
    disableMember,
    enableMember,
    error,
    forcePasswordChange,
    loadMembers,
    members,
    message,
    newMember,
    resetDrafts,
    resetPassword,
    runMemberAction,
    setDisableDrafts,
    setNewMember,
    setResetDrafts
  };
}
