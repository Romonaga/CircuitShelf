import type { QueryOptions, RetrievalStrategy } from "./query";

export type View = "ask" | "bench" | "finder" | "inventory" | "documents" | "corpus" | "review" | "trace" | "status" | "performance" | "work" | "aiUsage" | "settings" | "runtime" | "entity" | "account";

export interface EntityContext {
  id: number;
  name: string;
  slug: string;
  role: string;
  roleName: string;
  canManage: boolean;
  ownerUserId?: number | null;
}

export interface SessionUser {
  userId?: number;
  username: string;
  isAdmin: boolean;
  canManageSystem?: boolean;
  forcePasswordChange?: boolean;
  entity?: EntityContext | null;
  token: string;
  lastActivityAt?: number;
}

export interface AccountProfile {
  userId: number;
  username: string;
  email: string;
  displayName: string;
  nickname: string;
  phone: string;
  address: string;
  isAdmin: boolean;
  canManageSystem: boolean;
  forcePasswordChange: boolean;
  passwordChangedAt?: string | null;
  lastLoginAt?: string | null;
}

export interface AppConfig {
  siteName: string;
  models: string[];
  defaultModel: string;
  authConfigured: boolean;
  retrievalStrategies: RetrievalStrategy[];
  statusPollIntervalSeconds: number;
  activeStatusPollIntervalSeconds: number;
  sessionTimeoutSeconds: number;
  defaults: QueryOptions;
}

export interface EntityMember {
  userId: number;
  username: string;
  email?: string | null;
  displayName?: string | null;
  nickname?: string | null;
  isActive: boolean;
  canManageSystem: boolean;
  forcePasswordChange?: boolean;
  failedLoginCount?: number;
  disabledAt?: string | null;
  disabledReason?: string | null;
  role: string;
  roleName: string;
  canManage: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PasswordPolicy {
  id?: number;
  entityId?: number | null;
  minLength: number;
  requireUpper: boolean;
  requireLower: boolean;
  requireNumber: boolean;
  requireSymbol: boolean;
  passwordChangeDays: number;
  maxFailedAttempts: number;
  lockoutMinutes: number;
  updatedAt?: string | null;
}
