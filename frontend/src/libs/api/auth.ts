import type { AccountProfile, AppConfig, EntityContext } from "../../types";
import { requestJson } from "./core";

export function getAppConfig(): Promise<AppConfig> {
  return requestJson<AppConfig>("/api/app-config");
}

export function login(username: string, password: string): Promise<{ ok: boolean; userId?: number; username?: string; isAdmin?: boolean; canManageSystem?: boolean; forcePasswordChange?: boolean; entity?: EntityContext | null; token?: string; error?: string }> {
  return requestJson("/api/login", {
    method: "POST",
    body: JSON.stringify({ username, password })
  });
}

export function getMe(): Promise<{ userId?: number; username: string; isAdmin: boolean; canManageSystem?: boolean; forcePasswordChange?: boolean; entity?: EntityContext | null; profile?: AccountProfile | null }> {
  return requestJson("/api/me");
}

export function logout(): Promise<{ ok: boolean }> {
  return requestJson("/api/logout", { method: "POST" });
}
