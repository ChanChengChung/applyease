import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  authFetch,
  confirmEmail,
  forgotPassword,
  login,
  logout,
  register,
  resetPassword,
} from "./authApi";

describe("web auth API", () => {
  const values = new Map<string, string>();

  const fakeStorage = {
    getItem: vi.fn((key: string) => values.get(key) ?? null),
    setItem: vi.fn((key: string, value: string) => values.set(key, value)),
    removeItem: vi.fn((key: string) => values.delete(key)),
    clear: vi.fn(() => values.clear()),
    key: vi.fn(),
    length: 0,
  } as unknown as Storage;
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.clearAllMocks();
    values.clear();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: fakeStorage,
    });

    document.cookie = "applyease_csrf=; Max-Age=0; Path=/";
  });

  it("uses credentialed HttpOnly-cookie login without persisting the returned token", async () => {
    const fetchMock = vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          access_token: null,
          token_type: "bearer",
          user: {
            id: 1,
            email: "student@example.com",
            is_active: true,
            created_at: "2026-01-01",
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );

    await login("student@example.com", "a-secure-passphrase");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/login"),
      expect.objectContaining({ credentials: "include" }),
    );

    expect(fakeStorage.setItem).not.toHaveBeenCalled();
  });

  it("adds the bound CSRF header to cookie-authenticated mutations", async () => {
    document.cookie = "applyease_csrf=csrf-value; Path=/";

    const fetchMock = vi
      .spyOn(window, "fetch")
      .mockResolvedValue(new Response("{}", { status: 200 }));

    await authFetch("http://127.0.0.1:8000/api/v1/jobs/analyze", {
      method: "POST",
    });

    const init = fetchMock.mock.calls[0][1]!;

    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("csrf-value");

    expect(init.credentials).toBe("include");
  });

  it("revokes the server session on logout", async () => {
    document.cookie = "applyease_csrf=csrf-value; Path=/";

    const fetchMock = vi
      .spyOn(window, "fetch")
      .mockResolvedValue(new Response(null, { status: 204 }));

    await logout();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/logout"),
      expect.objectContaining({ method: "POST", credentials: "include" }),
    );
  });

  it("calls public account lifecycle endpoints with credentialed JSON requests", async () => {
    // NOTE: each call must return a *fresh* Response instance. The shared API
    // helper reads response.json() on every call; reusing one Response object
    // would exhaust its body stream and fail the second read.
    const fetchMock = vi.spyOn(window, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ message: "ok" }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await forgotPassword("student@example.com");

    await confirmEmail("verification-token-value-that-is-long-enough");

    await resetPassword(
      "reset-token-value-that-is-long-enough",
      "new-secure-password",
    );

    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual(
      expect.arrayContaining([
        expect.stringContaining("/auth/password/forgot"),
        expect.stringContaining("/auth/email-verification/confirm"),
        expect.stringContaining("/auth/password/reset"),
      ]),
    );

    for (const [, init] of fetchMock.mock.calls)
      expect(init).toEqual(
        expect.objectContaining({ method: "POST", credentials: "include" }),
      );
  });

  it("turns backend auth failures into stable UI error codes", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid email or password" }), {
        status: 401,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await expect(
      login("student@example.com", "wrong-password"),
    ).rejects.toMatchObject({ code: "auth_error_invalid_credentials" });

    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({ detail: "An account with this email already exists" }),
        {
          status: 409,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );
    await expect(
      register("student@example.com", "a-secure-passphrase"),
    ).rejects.toMatchObject({ code: "auth_error_email_exists" });
  });
});
