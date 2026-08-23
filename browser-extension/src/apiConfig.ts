export const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";
export const API_BASE_URL_KEY = "applyeaseApiBaseUrl";
export const API_ACCESS_TOKEN_KEY = "applyeaseAccessToken";

type WritableStorage = {
  set(values: Record<string, string>): Promise<void>;
  remove(key: string): Promise<void>;
};

export function normalizeApiBaseUrl(raw: string): string {
  const value = raw.trim();
  if (!value || value.length > 2048) throw new Error("请输入有效的后端地址");
  let url: URL;
  try { url = new URL(value); } catch { throw new Error("后端地址格式不正确"); }
  if (!['http:', 'https:'].includes(url.protocol)) throw new Error("后端地址必须使用 HTTP 或 HTTPS");
  if (url.protocol === "http:" && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error("远程后端必须使用 HTTPS");
  if (url.username || url.password) throw new Error("后端地址不能包含用户名或密码");
  url.hash = ""; url.search = "";
  const path = url.pathname.replace(/\/+$/, "").replace(/\/api\/v1$/, "");
  url.pathname = path || "/";
  return url.toString().replace(/\/$/, "");
}

export function apiOriginPattern(baseUrl: string): string {
  const url = new URL(normalizeApiBaseUrl(baseUrl));
  return `${url.protocol}//${url.host}/*`;
}

/**
 * Persist a new server only after dropping the bearer token for the previous
 * one. A token is audience-bound in product terms, even if it is structurally
 * valid elsewhere; retaining it would risk sending it to a newly entered URL.
 */
export async function saveApiBaseUrl(storage: WritableStorage, raw: string): Promise<string> {
  const normalized = normalizeApiBaseUrl(raw);
  await storage.set({ [API_BASE_URL_KEY]: normalized });
  await storage.remove(API_ACCESS_TOKEN_KEY);
  return normalized;
}

export async function getApiBaseUrl(storage: { get(keys: string): Promise<Record<string, unknown>> }): Promise<string> {
  const stored = await storage.get(API_BASE_URL_KEY);
  const value = stored[API_BASE_URL_KEY];
  return typeof value === "string" ? normalizeApiBaseUrl(value) : DEFAULT_API_BASE_URL;
}

export async function getAuthHeaders(storage: { get(keys: string): Promise<Record<string, unknown>> }): Promise<Record<string, string>> {
  const stored = await storage.get(API_ACCESS_TOKEN_KEY);
  const token = stored[API_ACCESS_TOKEN_KEY];
  return typeof token === "string" && token ? { Authorization: `Bearer ${token}` } : {};
}
