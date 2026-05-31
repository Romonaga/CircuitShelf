import { FormEvent, useState } from "react";
import { getAccountAIProvider, updateAccountAIProvider, updateAccountPassword } from "../api";
import type { ThemeMode } from "../hooks/useThemePreference";
import { errorMessage } from "../lib/errors";
import { AIProviderSettingsPanel } from "./AIProviderSettingsPanel";
import { ErrorMessage } from "./ErrorMessage";
import { SectionHeader } from "./SectionHeader";

export function AccountView({
  username,
  theme,
  setTheme
}: {
  username: string;
  theme: ThemeMode;
  setTheme: (theme: ThemeMode) => void;
}) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    setMessage("");
    setError("");
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      await updateAccountPassword({ currentPassword, newPassword });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Password updated.");
    } catch (err) {
      setError(errorMessage(err, "Could not update password"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="account-workflow">
      <header className="account-hero-panel">
        <SectionHeader title="Account" description={`Personal controls for ${username}.`} />
        <div className="theme-switcher" aria-label="Theme">
          <button className={theme === "light" ? "active" : ""} type="button" onClick={() => setTheme("light")}>
            Light bench
          </button>
          <button className={theme === "dark" ? "active" : ""} type="button" onClick={() => setTheme("dark")}>
            Dark bench
          </button>
        </div>
      </header>

      <form className="account-card" onSubmit={submitPassword}>
        <SectionHeader title="Change password" description="Keeps your local CircuitShelf login private." />
        <label>
          Current password
          <input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" />
        </label>
        <label>
          New password
          <input type="password" value={newPassword} minLength={8} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" />
        </label>
        <label>
          Confirm new password
          <input type="password" value={confirmPassword} minLength={8} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" />
        </label>
        <ErrorMessage message={error} />
        {message ? <div className="success-message">{message}</div> : null}
        <button className="primary-button" disabled={busy || !currentPassword || newPassword.length < 8 || !confirmPassword}>
          {busy ? "Updating..." : "Update password"}
        </button>
      </form>

      <AIProviderSettingsPanel
        title="Personal OpenAI key"
        description="Optional bring-your-own-key settings. Personal usage is tracked separately from entity-paid work."
        loadSettings={getAccountAIProvider}
        saveSettings={updateAccountAIProvider}
        canManage
        showBudget
      />
    </section>
  );
}
