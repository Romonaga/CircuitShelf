import { FormEvent, useState } from "react";
import { login } from "../api";
import type { SessionUser } from "../types";
import { errorMessage } from "../lib/errors";
import { ErrorMessage } from "./ErrorMessage";

export function LoginView({ siteName, onLogin }: { siteName: string; onLogin: (session: SessionUser) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const result = await login(username, password);
      if (!result.ok) {
        setError(result.error || "Invalid credentials");
        return;
      }
      onLogin({
        userId: result.userId,
        username: result.username || username,
        isAdmin: Boolean(result.isAdmin),
        token: result.token || ""
      });
    } catch (err) {
      setError(errorMessage(err, "Login failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <form className="login-panel" onSubmit={submit}>
        <div>
          <h1>{siteName}</h1>
          <p>Local electronics knowledge base</p>
        </div>
        <label>
          User
          <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        <ErrorMessage message={error} />
        <button className="primary-button" disabled={busy || !username || !password}>
          {busy ? "Checking..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}
