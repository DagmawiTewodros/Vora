// Thin fetch wrapper: adds the JWT, refreshes it once on 401, and turns DRF
// error bodies into readable messages.

const TOKEN_KEY = "vora.tokens";

export type User = {
  id: number;
  username: string;
  first_name: string;
  last_name: string;
  role: string;
  preferred_language: "en" | "am";
  is_manager: boolean;
};

type Tokens = { access: string; refresh: string; user: User };

function read<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

function write(key: string, value: unknown) {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: session lasts until reload */
  }
}

let tokens: Tokens | null = read<Tokens>(TOKEN_KEY);

export function currentUser(): User | null {
  return tokens?.user ?? null;
}

export function saveSession(t: Tokens) {
  tokens = t;
  write(TOKEN_KEY, t);
}

export function clearSession() {
  tokens = null;
  write(TOKEN_KEY, null);
}

export class ApiError extends Error {
  status: number;
  data: unknown;
  constructor(status: number, data: unknown) {
    super(formatError(data) || `Request failed (${status})`);
    this.status = status;
    this.data = data;
  }
}

function formatError(data: unknown): string {
  if (!data) return "";
  if (typeof data === "string") return data;
  if (Array.isArray(data)) return data.map(formatError).join(" ");
  if (typeof data === "object") {
    return Object.entries(data as Record<string, unknown>)
      .map(([k, v]) => (k === "detail" || k === "non_field_errors" ? formatError(v) : `${k.replace(/_/g, " ")}: ${formatError(v)}`))
      .join(" ");
  }
  return String(data);
}

async function refresh(): Promise<boolean> {
  if (!tokens?.refresh) return false;
  const res = await fetch("/api/auth/refresh/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: tokens.refresh }),
  });
  if (!res.ok) return false;
  const data = await res.json();
  saveSession({ ...tokens, access: data.access });
  return true;
}

export async function api<T = any>(path: string, options: { method?: string; body?: unknown } = {}, retry = true): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (tokens?.access) headers.Authorization = `Bearer ${tokens.access}`;
  const res = await fetch(`/api${path}`, {
    method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  if (res.status === 401 && retry && (await refresh())) return api<T>(path, options, false);
  if (res.status === 401 && tokens) {
    clearSession();
    window.location.assign("/login");
  }
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export const post = <T = any>(path: string, body: unknown = {}) => api<T>(path, { method: "POST", body });
export const patch = <T = any>(path: string, body: unknown) => api<T>(path, { method: "PATCH", body });
