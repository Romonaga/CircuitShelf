import { requestJson } from "./core";

export function getUserPreference<T>(key: string): Promise<{ key: string; value: T }> {
  return requestJson<{ key: string; value: T }>(`/api/user/preferences/${encodeURIComponent(key)}`);
}

export function updateUserPreference<T>(key: string, value: T): Promise<{ key: string; value: T }> {
  return requestJson<{ key: string; value: T }>(`/api/user/preferences/${encodeURIComponent(key)}`, {
    method: "PUT",
    body: JSON.stringify({ value })
  });
}
