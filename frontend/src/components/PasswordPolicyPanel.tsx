import { FormEvent, useEffect, useState } from "react";
import type { PasswordPolicy } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

const defaultPolicy: PasswordPolicy = {
  minLength: 12,
  requireUpper: true,
  requireLower: true,
  requireNumber: true,
  requireSymbol: false,
  passwordChangeDays: 0,
  maxFailedAttempts: 5,
  lockoutMinutes: 30
};

export function PasswordPolicyPanel({
  title,
  description,
  loadPolicy,
  savePolicy,
  canManage
}: {
  title: string;
  description: string;
  loadPolicy: () => Promise<{ policy: PasswordPolicy }>;
  savePolicy: (policy: PasswordPolicy) => Promise<{ policy: PasswordPolicy }>;
  canManage: boolean;
}) {
  const [policy, setPolicy] = useState<PasswordPolicy>(defaultPolicy);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setBusy(true);
    loadPolicy()
      .then((response) => {
        if (active) {
          setPolicy(response.policy);
        }
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load password policy"));
        }
      })
      .finally(() => {
        if (active) {
          setBusy(false);
        }
      });
    return () => {
      active = false;
    };
  }, [loadPolicy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canManage) {
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await savePolicy(policy);
      setPolicy(response.policy);
      setMessage("Password policy saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save password policy"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="policy-panel" onSubmit={submit}>
      <SectionHeader title={title} description={busy ? "Loading..." : description} />
      <ErrorMessage message={error} />
      <div className="policy-grid">
        <label>
          Minimum length
          <input
            type="number"
            min={8}
            max={128}
            value={policy.minLength}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, minLength: Number(event.target.value) })}
          />
        </label>
        <label>
          Change interval days
          <input
            type="number"
            min={0}
            value={policy.passwordChangeDays}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, passwordChangeDays: Number(event.target.value) })}
          />
        </label>
        <label>
          Failed attempts
          <input
            type="number"
            min={1}
            max={100}
            value={policy.maxFailedAttempts}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, maxFailedAttempts: Number(event.target.value) })}
          />
        </label>
        <label>
          Lockout minutes
          <input
            type="number"
            min={0}
            value={policy.lockoutMinutes}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, lockoutMinutes: Number(event.target.value) })}
          />
        </label>
      </div>
      <div className="policy-checks">
        <label className="inline-check">
          <input
            type="checkbox"
            checked={policy.requireUpper}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, requireUpper: event.target.checked })}
          />
          Uppercase
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={policy.requireLower}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, requireLower: event.target.checked })}
          />
          Lowercase
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={policy.requireNumber}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, requireNumber: event.target.checked })}
          />
          Number
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={policy.requireSymbol}
            disabled={!canManage}
            onChange={(event) => setPolicy({ ...policy, requireSymbol: event.target.checked })}
          />
          Symbol
        </label>
      </div>
      {message ? <p className="success-message">{message}</p> : null}
      {canManage ? (
        <button className="primary-button" disabled={saving || busy}>
          {saving ? "Saving..." : "Save policy"}
        </button>
      ) : null}
    </form>
  );
}
