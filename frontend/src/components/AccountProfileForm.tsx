import { FormEvent, useEffect, useState } from "react";
import { getMe, updateAccountProfile } from "../api";
import type { AccountProfile } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

const emptyProfile: AccountProfile = {
  userId: 0,
  username: "",
  email: "",
  displayName: "",
  nickname: "",
  phone: "",
  address: "",
  isAdmin: false,
  canManageSystem: false,
  forcePasswordChange: false
};

export function AccountProfileForm() {
  const [profile, setProfile] = useState<AccountProfile>(emptyProfile);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setBusy(true);
    getMe()
      .then((response) => {
        if (active && response.profile) {
          setProfile(response.profile);
        }
      })
      .catch((err) => {
        if (active) {
          setError(errorMessage(err, "Could not load profile"));
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
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const response = await updateAccountProfile(profile);
      setProfile(response.profile);
      setMessage("Profile saved.");
    } catch (err) {
      setError(errorMessage(err, "Could not save profile"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="account-card" onSubmit={submit}>
      <SectionHeader title="Profile" description={busy ? "Loading..." : "Your contact and display information."} />
      <div className="account-profile-grid">
        <label>
          Display name
          <input value={profile.displayName} onChange={(event) => setProfile({ ...profile, displayName: event.target.value })} />
        </label>
        <label>
          Nickname
          <input value={profile.nickname} onChange={(event) => setProfile({ ...profile, nickname: event.target.value })} />
        </label>
        <label>
          Email
          <input type="email" value={profile.email} onChange={(event) => setProfile({ ...profile, email: event.target.value })} />
        </label>
        <label>
          Phone
          <input value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} />
        </label>
      </div>
      <label>
        Address
        <textarea value={profile.address} rows={3} onChange={(event) => setProfile({ ...profile, address: event.target.value })} />
      </label>
      <div className="profile-meta">
        <span>Username: {profile.username || "n/a"}</span>
        <span>Password changed: {profile.passwordChangedAt ? new Date(profile.passwordChangedAt).toLocaleString() : "n/a"}</span>
        <span>Last login: {profile.lastLoginAt ? new Date(profile.lastLoginAt).toLocaleString() : "n/a"}</span>
      </div>
      <ErrorMessage message={error} />
      {message ? <div className="success-message">{message}</div> : null}
      <button className="primary-button" disabled={saving || busy}>
        {saving ? "Saving..." : "Save profile"}
      </button>
    </form>
  );
}
