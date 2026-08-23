import { useEffect, useState } from "react";
import {
  confirmEmail,
  forgotPassword,
  login,
  register,
  requestEmailVerification,
  resetPassword,
  verifyMfaLogin,
} from "../../services/authApi";
import { useI18n, useT } from "../../i18n/LanguageProvider";
import { LANGUAGES } from "../../i18n";

type Mode =
  "login" | "register" | "forgot" | "reset" | "verifying" | "mfa" | "message";

type MessageKind =
  "default" | "verification-pending" | "reset-request" | "reset-complete";

function authToken(name: string): string {
  try {
    // New email links use the fragment, which is never sent to Caddy/Nginx.
    // Keep query-string support briefly so a previously issued email still works.
    const fragment = window.location.hash.startsWith("#")
      ? window.location.hash.slice(1)
      : "";
    return (
      new URLSearchParams(fragment).get(name)?.trim() ||
      new URLSearchParams(window.location.search).get(name)?.trim() ||
      ""
    );
  } catch {
    return "";
  }
}

function clearAuthTokens(): void {
  try {
    const url = new URL(window.location.href);
    url.searchParams.delete("verify_token");
    url.searchParams.delete("reset_token");
    const fragment = new URLSearchParams(
      url.hash.startsWith("#") ? url.hash.slice(1) : "",
    );
    const hadAuthToken =
      fragment.has("verify_token") || fragment.has("reset_token");
    fragment.delete("verify_token");
    fragment.delete("reset_token");
    if (hadAuthToken)
      url.hash = fragment.toString() ? `#${fragment.toString()}` : "";
    window.history.replaceState(
      {},
      "",
      `${url.pathname}${url.search}${url.hash}`,
    );
  } catch {
    // A malformed URL must not prevent returning to sign-in.
  }
}

export function AuthPage({ onAuthenticated }: { onAuthenticated: () => void }) {
  const resetToken = authToken("reset_token");
  const verifyToken = authToken("verify_token");

  const [mode, setMode] = useState<Mode>(
    verifyToken ? "verifying" : resetToken ? "reset" : "login",
  );

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [mfaToken, setMfaToken] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetRequested, setResetRequested] = useState(false);
  const [messageKind, setMessageKind] = useState<MessageKind>("default");

  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);

  const t = useT();
  const { language, setLanguage } = useI18n();

  // Localize an auth error:
  //  - A plain Error (e.g. a client-side validation like password mismatch) is
  //    already a user-facing, localized message -> show it as-is.
  //  - An AuthError-shaped object ({ code, message }) comes from the API layer:
  //    prefer the backend `detail` (business-specific), otherwise map the error
  //    code to an i18n string. Never show raw codes.
  //
  // We use duck-typing (checking for `.code`) instead of `instanceof AuthError`
  // so this stays robust even when authApi is mocked in tests (the mock may not
  // export the AuthError class).
  const errorText = (e: unknown): string => {
    if (e instanceof Error && !(e as { code?: string }).code) {
      return e.message;
    }
    const err = e as { code?: string; message?: string } | null;
    if (err && typeof err.code === "string") {
      const errorKeys: Record<string, string> = {
        auth_error_login_failed: "auth.error.loginFailed",
        auth_error_register_failed: "auth.error.registerFailed",
        auth_error_request_failed: "auth.error.requestFailed",
        auth_error_invalid_credentials: "auth.error.invalidCredentials",
        auth_error_email_unverified: "auth.error.emailUnverified",
        auth_error_email_exists: "auth.error.emailExists",
        auth_error_invalid_input: "auth.error.invalidInput",
        auth_error_invalid_token: "auth.error.invalidToken",
        auth_error_rate_limited: "auth.error.rateLimited",
      };
      return t(errorKeys[err.code] ?? "auth.authFailed");
    }
    return t("auth.authFailed");
  };

  useEffect(() => {
    if (!verifyToken) return;

    setBusy(true);
    setError("");

    void confirmEmail(verifyToken)
      .then((result) => {
        clearAuthTokens();
        setNotice(result.message);
        setMessageKind("default");
        setMode("message");
      })
      .catch((err) => {
        setError(errorText(err));
        setMode("message");
      })

      .finally(() => setBusy(false));
  }, [verifyToken]);

  const clearMessages = () => {
    setError("");
    setNotice("");
  };

  const changeMode = (next: Mode) => {
    clearAuthTokens();
    clearMessages();
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
    setShowConfirmPassword(false);
    setResetCode("");
    setMessageKind("default");
    setMode(next);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true);
    clearMessages();

    try {
      if (mode === "login") {
        const result = await login(email, password);
        if (result.mfa_required && result.mfa_token) {
          setMfaToken(result.mfa_token);
          setMfaCode("");
          setMode("mfa");
        } else onAuthenticated();
      } else if (mode === "mfa") {
        await verifyMfaLogin(mfaToken, mfaCode);
        onAuthenticated();
      } else if (mode === "register") {
        if (password !== confirmPassword)
          throw new Error(t("auth.passwordMismatch"));
        const result = await register(email, password);

        if (result.session_ready) onAuthenticated();
        else {
          setNotice(t("auth.created"));
          setMessageKind("verification-pending");
          setMode("message");
        }
      } else if (mode === "forgot") {
        const result = await forgotPassword(email);
        setResetRequested(true);
        setNotice(
          result.delivery_channel === "local_mailbox"
            ? t("auth.resetLocalMailbox")
            : result.delivery_channel === "disabled"
              ? t("auth.resetDeliveryDisabled")
              : t("auth.resetEmailSent"),
        );
        setMessageKind("reset-request");
        setMode("message");
      } else if (mode === "reset") {
        if (password !== confirmPassword)
          throw new Error(t("auth.passwordMismatch"));

        const recoveryToken = resetToken || resetCode.trim();
        if (!recoveryToken) throw new Error(t("auth.resetCodeRequired"));
        await resetPassword(recoveryToken, password);
        clearAuthTokens();
        setResetRequested(false);
        setNotice(t("auth.resetComplete"));
        setMessageKind("reset-complete");
        setMode("message");
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    if (!email) {
      setError(t("auth.emailRequired"));
      return;
    }

    setBusy(true);
    clearMessages();

    try {
      const result = await requestEmailVerification(email);
      setNotice(result.message);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const resendResetCode = async () => {
    if (!email) {
      setError(t("auth.emailRequired"));
      return;
    }

    setBusy(true);
    clearMessages();
    try {
      const result = await forgotPassword(email);
      setResetRequested(true);
      setResetCode("");
      setNotice(
        result.delivery_channel === "local_mailbox"
          ? t("auth.resetLocalMailbox")
          : result.delivery_channel === "disabled"
            ? t("auth.resetDeliveryDisabled")
            : t("auth.resetCodeResent"),
      );
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const title =
    mode === "login"
      ? t("auth.login")
      : mode === "mfa"
        ? t("auth.mfa.title")
        : mode === "register"
          ? t("auth.register")
          : mode === "forgot"
            ? t("auth.forgot")
            : mode === "reset"
              ? t("auth.reset")
              : mode === "verifying"
                ? t("auth.verifying")
                : messageKind === "reset-complete"
                  ? t("auth.resetCompleteTitle")
                  : t("auth.checkEmail");

  const passwordMode =
    mode === "login" || mode === "register" || mode === "reset";
  const needsStrongPassword = mode === "register" || mode === "reset";
  const passwordLongEnough = password.length >= 12;
  const passwordsMatch =
    Boolean(confirmPassword) && password === confirmPassword;
  // Keep reset available once the password is long enough: submitting a mismatch
  // gives an explicit accessible error instead of a silent disabled button.
  const canSubmit = !busy && (!needsStrongPassword || passwordLongEnough);

  return (
    <main className="auth-page">
      <section className="auth-shell">
        <aside className="auth-aside">
          <span className="auth-aside-glow" aria-hidden="true" />
          <div className="auth-aside-content">
            <div className="auth-product-lockup">
              <span className="auth-product-name">
                <b>Apply</b>
                <b>Ease</b>
              </span>
              <span className="auth-product-chip">AI APPLICATION OS</span>
            </div>
            <p className="eyebrow">{t("auth.hero.eyebrow")}</p>
            <h1>{t("auth.hero.title")}</h1>
            <p className="auth-aside-sub">{t("auth.hero.sub")}</p>
            <ul className="auth-trust-list">
              <li>
                <span aria-hidden="true">✓</span>
                {t("auth.trust.experience")}
              </li>
              <li>
                <span aria-hidden="true">✓</span>
                {t("auth.trust.sources")}
              </li>
              <li>
                <span aria-hidden="true">✓</span>
                {t("auth.trust.isolation")}
              </li>
            </ul>
            <div className="auth-aside-footer">
              <span className="auth-status-dot" aria-hidden="true" />
              {t("auth.workspace")}
            </div>
          </div>
        </aside>
        <section className="card auth-form" aria-live="polite">
          <div className="auth-form-top">
            <div
              className="auth-language"
              role="group"
              aria-label={t("nav.language")}
            >
              {LANGUAGES.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className={language === item.code ? "active" : ""}
                  aria-pressed={language === item.code}
                  onClick={() => setLanguage(item.code)}
                >
                  {item.code === "zh-CN"
                    ? "简"
                    : item.code === "zh-TW"
                      ? "繁"
                      : "EN"}
                </button>
              ))}
            </div>
          </div>
          <div className="auth-heading">
            <span className="auth-lock">✦</span>
            <div>
              <p className="eyebrow">{t("auth.workspace")}</p>
              <h2>{title}</h2>
            </div>
          </div>
          {mode === "verifying" ? (
            <p>{busy ? t("auth.verifyingWait") : t("auth.verified")}</p>
          ) : mode === "message" ? (
            <>
              {notice && <p className="feedback feedback-success">{notice}</p>}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <div className="actions">
                <button type="button" onClick={() => changeMode("login")}>
                  {t("auth.backToLogin")}
                </button>
                {messageKind === "verification-pending" && email && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void resend()}
                  >
                    {busy ? t("auth.resend") : t("auth.resend")}
                  </button>
                )}
                {messageKind === "reset-request" && resetRequested && (
                  <button type="button" onClick={() => changeMode("reset")}>
                    {t("auth.enterResetCode")}
                  </button>
                )}
              </div>
            </>
          ) : (
            <form onSubmit={submit}>
              {mode !== "reset" && mode !== "mfa" && (
                <label>
                  {t("auth.email")}
                  <input
                    type="email"
                    autoComplete="username"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </label>
              )}

              {mode === "reset" && !resetToken && (
                <div className="reset-code-field">
                  <label>
                    {t("auth.resetCode")}
                    <input
                      inputMode="numeric"
                      autoComplete="one-time-code"
                      required
                      minLength={6}
                      maxLength={6}
                      value={resetCode}
                      onChange={(event) =>
                        setResetCode(
                          event.target.value.replace(/\D/g, "").slice(0, 6),
                        )
                      }
                      placeholder={t("auth.resetCodePlaceholder")}
                    />
                  </label>
                  <button
                    className="auth-inline-action"
                    type="button"
                    disabled={busy}
                    onClick={() => void resendResetCode()}
                  >
                    {busy
                      ? t("auth.resendingResetCode")
                      : t("auth.resendResetCode")}
                  </button>
                </div>
              )}

              {mode === "mfa" && (
                <label>
                  {t("auth.mfa.code")}
                  <input
                    aria-label={t("auth.mfa.code")}
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    required
                    minLength={6}
                    maxLength={32}
                    value={mfaCode}
                    onChange={(e) => setMfaCode(e.target.value)}
                  />
                </label>
              )}

              {passwordMode && (
                <label>
                  {mode === "reset"
                    ? t("auth.newPassword")
                    : t("auth.password")}
                  <span className="password-field">
                    <input
                      type={showPassword ? "text" : "password"}
                      autoComplete={
                        mode === "login" ? "current-password" : "new-password"
                      }
                      required
                      minLength={mode === "login" ? 1 : 12}
                      maxLength={128}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      aria-label={
                        showPassword
                          ? t("auth.password.hide")
                          : t("auth.password.show")
                      }
                      title={
                        showPassword
                          ? t("auth.password.hide")
                          : t("auth.password.show")
                      }
                      onClick={() => setShowPassword((value) => !value)}
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
                        <circle cx="12" cy="12" r="2.6" />
                        {showPassword && <path d="m4 4 16 16" />}
                      </svg>
                    </button>
                  </span>
                </label>
              )}

              {needsStrongPassword && (
                <label>
                  {mode === "register"
                    ? t("auth.confirmRegistrationPassword")
                    : t("auth.confirmPassword")}
                  <span className="password-field">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      minLength={12}
                      maxLength={128}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                    />
                    <button
                      type="button"
                      className="password-toggle"
                      aria-label={
                        showConfirmPassword
                          ? t("auth.password.hide")
                          : t("auth.password.show")
                      }
                      title={
                        showConfirmPassword
                          ? t("auth.password.hide")
                          : t("auth.password.show")
                      }
                      onClick={() => setShowConfirmPassword((value) => !value)}
                    >
                      <svg viewBox="0 0 24 24" aria-hidden="true">
                        <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" />
                        <circle cx="12" cy="12" r="2.6" />
                        {showConfirmPassword && <path d="m4 4 16 16" />}
                      </svg>
                    </button>
                  </span>
                </label>
              )}

              {needsStrongPassword && (
                <div className="password-rules" aria-live="polite">
                  <strong>{t("auth.password.setup")}</strong>
                  <span
                    className={
                      passwordLongEnough ? "rule-pass" : "rule-pending"
                    }
                  >
                    {passwordLongEnough ? "✓" : "○"} {t("auth.password.length")}
                  </span>
                  <span
                    className={passwordsMatch ? "rule-pass" : "rule-pending"}
                  >
                    {passwordsMatch ? "✓" : "○"} {t("auth.password.match")}
                  </span>
                  <small>{t("auth.passwordHint")}</small>
                </div>
              )}

              {notice && <p className="feedback feedback-success">{notice}</p>}
              {error && (
                <p className="error" role="alert">
                  {error}
                </p>
              )}
              <button className="auth-primary" disabled={!canSubmit}>
                {busy
                  ? t("auth.processing")
                  : mode === "mfa"
                    ? t("auth.mfa.verify")
                    : mode === "login"
                      ? t("auth.login")
                      : mode === "register"
                        ? t("auth.create")
                        : mode === "forgot"
                          ? t("auth.sendReset")
                          : t("auth.doReset")}
              </button>

              {mode === "login" && (
                <div className="auth-links">
                  <a
                    href="#register"
                    onClick={(event) => {
                      event.preventDefault();
                      changeMode("register");
                    }}
                  >
                    {t("auth.noAccount")}
                  </a>
                  <span aria-hidden="true">·</span>
                  <a
                    href="#forgot-password"
                    onClick={(event) => {
                      event.preventDefault();
                      changeMode("forgot");
                    }}
                  >
                    {t("auth.forgotLink")}
                  </a>
                </div>
              )}

              {mode !== "login" && (
                <button type="button" onClick={() => changeMode("login")}>
                  {t("auth.backToLogin")}
                </button>
              )}
            </form>
          )}
        </section>
      </section>
    </main>
  );
}
