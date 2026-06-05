import type { View } from "../types";

export interface ViewAccessContext {
  authenticated: boolean;
  canManageEntity: boolean;
  canManageSystem: boolean;
}

const AUTHENTICATED_VIEWS = new Set<View>([
  "ask",
  "bench",
  "finder",
  "inventory",
  "documents",
  "trace",
  "status",
  "performance",
  "work",
  "aiUsage",
  "account"
]);

const ENTITY_ADMIN_VIEWS = new Set<View>(["entity", "review"]);
const SYSTEM_ADMIN_VIEWS = new Set<View>(["corpus", "settings", "runtime"]);

export function canAccessView(view: View, access: ViewAccessContext): boolean {
  if (!access.authenticated) {
    return false;
  }
  if (AUTHENTICATED_VIEWS.has(view)) {
    return true;
  }
  if (ENTITY_ADMIN_VIEWS.has(view)) {
    return access.canManageEntity || access.canManageSystem;
  }
  if (SYSTEM_ADMIN_VIEWS.has(view)) {
    return access.canManageSystem;
  }
  return false;
}

export function firstAccessibleView(access: ViewAccessContext): View {
  return canAccessView("ask", access) ? "ask" : "account";
}
