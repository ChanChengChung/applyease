const TOKEN_KEY = "applyease_access_token"; // legacy cleanup only; new web sessions use HttpOnly cookies.
const CSRF_COOKIE = "applyease_csrf";

export type AuthUser = {
  id: number;
  email: string;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
};
export type AuthResponse = {
  access_token: string | null;
  token_type: string;
  user: AuthUser;
  mfa_required?: boolean;
  mfa_token?: string | null;
  session_ready?: boolean;
};
export type PublicMessage = {
  message: string;
  // This is transport configuration, not an account-existence signal.
  delivery_channel?: "email" | "local_mailbox" | "disabled";
};
export type MFAStatus = { enabled: boolean; recovery_codes_remaining: number };
export type MFASetup = { secret: string; provisioning_uri: string };
export type MFARecoveryCodes = { recovery_codes: string[] };
export type AuthSession = {
  id: string;
  created_at: string;
  last_seen_at: string;
  expires_at: string;
  current: boolean;
};

// Error codes thrown by this module. The UI maps these to localized
// messages via i18n (auth.error.*) so no human-language text is hardcoded here.
const AUTH_ERROR = {
  login: "auth_error_login_failed",
  register: "auth_error_register_failed",
  request: "auth_error_request_failed",
  session: "auth_error_session_check_failed",
  logout: "auth_error_logout_failed",
  invalidCredentials: "auth_error_invalid_credentials",
  emailUnverified: "auth_error_email_unverified",
  emailExists: "auth_error_email_exists",
  invalidInput: "auth_error_invalid_input",
  invalidToken: "auth_error_invalid_token",
  rateLimited: "auth_error_rate_limited",
} as const;

export class AuthError extends Error {
  code: string;
  constructor(code: string, message?: string) {
    super(message ?? code);
    this.name = "AuthError";
    this.code = code;
  }
}

function fail(code: string, data: { detail?: string }): never {
  // When the backend provides a human-readable `detail`, surface it as-is
  // (it may carry business-specific info). Otherwise fall back to the code,
  // which the UI maps to a localized string.
  throw new AuthError(code, data.detail || undefined);
}

function authFailure(
  error: unknown,
  fallback: string,
  action: "login" | "register" | "public",
): never {
  if (!(error instanceof ApiRequestError)) fail(fallback, {});
  if (error.status === 429) fail(AUTH_ERROR.rateLimited, {});
  if (error.status === 422) fail(AUTH_ERROR.invalidInput, {});
  if (action === "login" && error.status === 401)
    fail(AUTH_ERROR.invalidCredentials, {});
  if (action === "login" && error.status === 403)
    fail(AUTH_ERROR.emailUnverified, {});
  if (action === "register" && error.status === 409)
    fail(AUTH_ERROR.emailExists, {});
  if (action === "public" && error.status === 400)
    fail(AUTH_ERROR.invalidToken, {});
  fail(fallback, {});
}
function storage(): Storage | null {
  try {
    return typeof window !== "undefined" &&
      typeof window.localStorage?.getItem === "function"
      ? window.localStorage
      : null;
  } catch {
    return null;
  }
}
export const getToken = () => storage()?.getItem(TOKEN_KEY) ?? null;
export const clearToken = () => storage()?.removeItem(TOKEN_KEY);
function csrfToken(): string {
  if (typeof document === "undefined") return "";

  const item = document.cookie
    .split(";")
    .map((value) => value.trim())
    .find((value) => value.startsWith(`${CSRF_COOKIE}=`));

  return item ? decodeURIComponent(item.slice(CSRF_COOKIE.length + 1)) : "";
}
function secureInit(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  const method = (init.method || "GET").toUpperCase();

  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const csrf = csrfToken();
  if (csrf && !["GET", "HEAD", "OPTIONS"].includes(method) && !token)
    headers.set("X-CSRF-Token", csrf);

  return { ...init, headers, credentials: "include" };
}
import { ApiRequestError, request } from "./request";

async function authenticate(
  path: "login" | "register",
  email: string,
  password: string,
): Promise<AuthResponse> {
  try {
    // request() throws ApiRequestError on non-OK; we translate it into the
    // localized AuthError code so the UI can map it to i18n.
    const data = await request<AuthResponse>(
      `/auth/${path}`,
      secureInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      }),
    );
    clearToken();
    return data;
  } catch (error) {
    authFailure(
      error,
      path === "login" ? AUTH_ERROR.login : AUTH_ERROR.register,
      path,
    );
  }
}
export const login = (email: string, password: string) =>
  authenticate("login", email, password);
export const register = (email: string, password: string) =>
  authenticate("register", email, password);
async function publicPost(
  path: string,
  body: Record<string, string>,
): Promise<PublicMessage> {
  try {
    return await request<PublicMessage>(
      `/auth/${path}`,
      secureInit({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    );
  } catch (error) {
    authFailure(error, AUTH_ERROR.request, "public");
  }
}
export const requestEmailVerification = (email: string) =>
  publicPost("email-verification/request", { email });
export const confirmEmail = (token: string) =>
  publicPost("email-verification/confirm", { token });
export const forgotPassword = (email: string) =>
  publicPost("password/forgot", { email });
export const resetPassword = (token: string, newPassword: string) =>
  publicPost("password/reset", { token, new_password: newPassword });
export async function verifyMfaLogin(
  mfaToken: string,
  code: string,
): Promise<AuthResponse> {
  return request<AuthResponse>(
    "/auth/mfa/login/verify",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mfa_token: mfaToken, code }),
    }),
  );
}
export const getMfaStatus = () => request<MFAStatus>("/auth/mfa", secureInit());
export const startMfaSetup = (currentPassword: string) =>
  request<MFASetup>(
    "/auth/mfa/setup",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_password: currentPassword }),
    }),
  );
export const confirmMfaSetup = (code: string) =>
  request<MFARecoveryCodes>(
    "/auth/mfa/confirm",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    }),
  );
export const rotateRecoveryCodes = (code: string) =>
  request<MFARecoveryCodes>(
    "/auth/mfa/recovery-codes",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    }),
  );
export const disableMfa = (code: string) =>
  request<void>(
    "/auth/mfa/disable",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    }),
    { parseJson: false },
  );
export const listSessions = () =>
  request<AuthSession[]>("/auth/sessions", secureInit());
export const revokeSession = (id: string) =>
  request<void>(`/auth/sessions/${id}`, secureInit({ method: "DELETE" }), {
    parseJson: false,
  });
export const changePassword = (
  currentPassword: string,
  newPassword: string,
  mfaCode = "",
) =>
  request<PublicMessage>(
    "/auth/password/change",
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        current_password: currentPassword,
        new_password: newPassword,
        ...(mfaCode ? { mfa_code: mfaCode } : {}),
      }),
    }),
  );
type SensitiveAction = { current_password: string; mfa_code?: string };
export async function downloadAccountData(
  currentPassword: string,
  mfaCode: string,
): Promise<{ blob: Blob; filename: string }> {
  const base = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";
  const payload: SensitiveAction = {
    current_password: currentPassword,
    ...(mfaCode ? { mfa_code: mfaCode } : {}),
  };
  const response = await fetch(
    `${base}/auth/data-export`,
    secureInit({
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  );
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new AuthError(AUTH_ERROR.request, error.detail);
  }
  const disposition = response.headers.get("Content-Disposition") || "";
  return {
    blob: await response.blob(),
    filename:
      disposition.match(/filename="?([^";]+)"?/i)?.[1] ||
      "ApplyEase-account-data.zip",
  };
}
export const deleteAccount = (currentPassword: string, mfaCode: string) => {
  const payload: SensitiveAction = {
    current_password: currentPassword,
    ...(mfaCode ? { mfa_code: mfaCode } : {}),
  };
  return request<void>(
    "/auth/account",
    secureInit({
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
    { parseJson: false },
  );
};
export function saveAccountDownload({
  blob,
  filename,
}: {
  blob: Blob;
  filename: string;
}) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
export async function checkSession(): Promise<AuthUser | null> {
  // Treat HTTP 401 as "no active session" rather than an error.
  return request<AuthUser>(`/auth/me`, secureInit(), { expectStatus: 401 });
}
export async function logout(): Promise<void> {
  clearToken();
  // 401 after logout just means the session is already gone — not an error.
  await request<void>(`/auth/logout`, secureInit({ method: "POST" }), {
    expectStatus: 401,
    parseJson: false,
  });
}
export async function authFetch(
  input: RequestInfo | URL,
  init: RequestInit = {},
) {
  return fetch(input, secureInit(init));
}

export function installAuthInterceptor() {
  if (
    typeof window === "undefined" ||
    (window as Window & { __applyEaseAuth?: boolean }).__applyEaseAuth
  )
    return;

  const nativeFetch = window.fetch.bind(window);

  window.fetch = async (input, init = {}) => {
    const prepared = secureInit(init);
    const token = getToken();

    const response = await nativeFetch(input, prepared);

    if (response.status === 401 && token) clearToken();

    if (
      response.status === 401 &&
      !String(input).includes("/auth/login") &&
      !String(input).includes("/auth/register") &&
      !String(input).includes("/auth/me")
    )
      window.dispatchEvent(new Event("applyease:unauthorized"));

    return response;
  };

  (window as Window & { __applyEaseAuth?: boolean }).__applyEaseAuth = true;
}
