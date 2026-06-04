const sessionStorageKey = "circuitshelf-session";

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const session = readSessionToken();
  const isFormData = init?.body instanceof FormData;
  const { headers: initHeaders, ...requestInit } = init ?? {};
  const response = await fetch(path, {
    ...requestInit,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(session ? { Authorization: `Bearer ${session}` } : {}),
      ...(initHeaders ?? {})
    }
  });

  const raw = await response.text();
  let data: T & { error?: string };
  try {
    data = raw ? (JSON.parse(raw) as T & { error?: string }) : ({} as T & { error?: string });
  } catch {
    const preview = raw.trim().slice(0, 160) || response.statusText;
    throw new Error(`Expected JSON from ${path}, got ${response.status} ${response.statusText}: ${preview}`);
  }

  if (!response.ok || data.error) {
    if (response.status === 401) {
      window.dispatchEvent(new Event("circuitshelf-auth-expired"));
    }
    throw new Error(data.error || `Request failed with status ${response.status}`);
  }
  return data as T;
}

export function readSessionToken(): string {
  try {
    const raw = window.localStorage.getItem(sessionStorageKey);
    if (!raw) {
      return "";
    }
    const session = JSON.parse(raw) as { token?: string };
    return session.token || "";
  } catch {
    return "";
  }
}

export { sessionStorageKey };
