import { useCallback, useEffect, useState } from "react";
import {
  changePassword,
  checkSession,
  confirmMfaSetup,
  deleteAccount,
  disableMfa,
  downloadAccountData,
  getMfaStatus,
  getReminderPreferences,
  listSessions,
  revokeSession,
  rotateRecoveryCodes,
  saveAccountDownload,
  startMfaSetup,
  updateReminderPreferences,
} from "../../services/authApi";
import type { AuthSession, AuthUser, ReminderPreferences } from "../../services/authApi";
import { useI18n, useT } from "../../i18n/LanguageProvider";

export function SecurityPage() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [remaining, setRemaining] = useState(0);
  const [secret, setSecret] = useState("");
  const [uri, setUri] = useState("");
  const [code, setCode] = useState("");
  const [codes, setCodes] = useState<string[]>([]);
  const [mfaSetupPassword, setMfaSetupPassword] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordMfa, setPasswordMfa] = useState("");
  const [sensitivePassword, setSensitivePassword] = useState("");
  const [sensitiveMfa, setSensitiveMfa] = useState("");
  const [deletePhrase, setDeletePhrase] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reminderPreferences, setReminderPreferences] =
    useState<ReminderPreferences | null>(null);
  const [reminderTimezone, setReminderTimezone] = useState("UTC");
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [reminderDays, setReminderDays] = useState(7);
  const [reminderHour, setReminderHour] = useState(9);
  const t = useT();
  const { language } = useI18n();
  const dateLocale =
    language === "zh-CN" ? "zh-CN" : language === "zh-TW" ? "zh-TW" : "en-US";
  const deleteKeyword = t("security.deleteKeyword");
  const load = useCallback(async () => {
    try {
      const [me, mfa, devices, reminders] = await Promise.all([
        checkSession(),
        getMfaStatus(),
        listSessions(),
        getReminderPreferences(),
      ]);
      setUser(me);
      setEnabled(mfa.enabled);
      setRemaining(mfa.recovery_codes_remaining);
      setSessions(devices);
      setReminderPreferences(reminders);
      setReminderTimezone(reminders.timezone);
      setReminderEnabled(reminders.enabled);
      setReminderDays(reminders.days_before);
      setReminderHour(reminders.local_hour);

      // A new account starts at UTC.  Capture the browser's IANA zone once so
      // the scheduler can interpret dates in the student's local time.  An
      // explicit non-UTC choice is always respected.
      const detected =
        typeof Intl !== "undefined"
          ? Intl.DateTimeFormat().resolvedOptions().timeZone
          : "";
      if (reminders.timezone === "UTC" && detected && detected !== "UTC") {
        try {
          const synced = await updateReminderPreferences({ timezone: detected });
          setReminderPreferences(synced);
          setReminderTimezone(synced.timezone);
        } catch {
          // The visible settings remain editable if automatic detection cannot
          // be persisted (for example, during an offline demo).
        }
      }
    } catch {
      setError(t("security.loadFailed"));
    }
  }, [t]);
  useEffect(() => {
    void load();
  }, [load]);
  const run = async (action: () => Promise<void>) => {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await action();
    } catch {
      setError(t("security.updateFailed"));
    } finally {
      setBusy(false);
    }
  };
  const setup = () =>
    run(async () => {
      const result = await startMfaSetup(mfaSetupPassword);
      setSecret(result.secret);
      setUri(result.provisioning_uri);
      setMfaSetupPassword("");
    });
  const confirm = () =>
    run(async () => {
      const result = await confirmMfaSetup(code);
      setCodes(result.recovery_codes);
      setSecret("");
      setUri("");
      setCode("");
      await load();
    });
  const rotate = () =>
    run(async () => {
      const result = await rotateRecoveryCodes(code);
      setCodes(result.recovery_codes);
      setCode("");
      await load();
    });
  const disable = () =>
    run(async () => {
      if (!window.confirm(t("security.confirmDisableMfa"))) return;
      await disableMfa(code);
      setCodes([]);
      setCode("");
      await load();
    });
  const removeDevice = (id: string) =>
    run(async () => {
      await revokeSession(id);
      await load();
    });
  const updatePassword = () =>
    run(async () => {
      if (newPassword !== confirmPassword) {
        setError(t("security.passwordMismatch"));
        return;
      }
      if (enabled && !passwordMfa) {
        setError(t("security.mfaCode"));
        return;
      }
      if (enabled)
        await changePassword(currentPassword, newPassword, passwordMfa);
      else await changePassword(currentPassword, newPassword);
      setNotice(t("security.passwordUpdated"));
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setPasswordMfa("");
      window.dispatchEvent(new Event("applyease:unauthorized"));
    });
  const exportData = () =>
    run(async () => {
      saveAccountDownload(
        await downloadAccountData(sensitivePassword, sensitiveMfa),
      );
      setNotice(t("security.exported"));
    });
  const saveReminderPreferences = () =>
    run(async () => {
      const saved = await updateReminderPreferences({
        timezone: reminderTimezone,
        enabled: reminderEnabled,
        days_before: reminderDays,
        local_hour: reminderHour,
      });
      setReminderPreferences(saved);
      setReminderTimezone(saved.timezone);
      setReminderEnabled(saved.enabled);
      setReminderDays(saved.days_before);
      setReminderHour(saved.local_hour);
      setNotice(t("security.reminderSaved"));
    });
  const removeAccount = () =>
    run(async () => {
      if (deletePhrase !== deleteKeyword) {
        setError(t("security.deleteMismatch"));
        return;
      }
      if (!window.confirm(t("security.confirmDelete"))) return;
      await deleteAccount(sensitivePassword, sensitiveMfa);
      window.dispatchEvent(new Event("applyease:unauthorized"));
    });
  return (
    <main>
      <header>
        <p className="eyebrow">{t("security.eyebrow")}</p>
        <h1>{t("security.hero.title")}</h1>
        <p className="sub">{t("security.hero.sub")}</p>
      </header>
      <section aria-live="polite">
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {notice && <p className="feedback feedback-success">{notice}</p>}
        <article className="card">
          <h2>{t("security.account")}</h2>
          {user ? (
            <p>
              <strong>{user.email}</strong> ·{" "}
              {user.email_verified
                ? t("security.emailVerified")
                : t("security.emailPending")}
            </p>
          ) : (
            <p>{t("security.loadingAccount")}</p>
          )}
        </article>
        <article className="card security-reminder-settings">
          <h2>{t("security.deadlineReminders")}</h2>
          <p>{t("security.deadlineRemindersDescription")}</p>
          <label>
            {t("security.reminderTimezone")}
            <input
              aria-label={t("security.reminderTimezone")}
              value={reminderTimezone}
              onChange={(event) => setReminderTimezone(event.target.value)}
              placeholder="Asia/Hong_Kong"
            />
          </label>
          <label>
            {t("security.reminderDays")}
            <input
              aria-label={t("security.reminderDays")}
              type="number"
              min={0}
              max={30}
              value={reminderDays}
              onChange={(event) => setReminderDays(Number(event.target.value))}
            />
          </label>
          <label>
            {t("security.reminderHour")}
            <input
              aria-label={t("security.reminderHour")}
              type="number"
              min={0}
              max={23}
              value={reminderHour}
              onChange={(event) => setReminderHour(Number(event.target.value))}
            />
          </label>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={reminderEnabled}
              onChange={(event) => setReminderEnabled(event.target.checked)}
            />
            {t("security.reminderEnabled")}
          </label>
          {reminderPreferences && (
            <small>
              {t("security.reminderDestination", {
                email: reminderPreferences.email,
                mode: reminderPreferences.delivery_mode,
              })}
            </small>
          )}
          <button
            type="button"
            disabled={busy || !reminderTimezone || reminderDays < 0 || reminderDays > 30 || reminderHour < 0 || reminderHour > 23}
            onClick={() => void saveReminderPreferences()}
          >
            {busy ? t("security.processing") : t("security.saveReminderSettings")}
          </button>
        </article>
        <article className="card">
          <h2>{t("security.changePassword")}</h2>
          <p>{t("security.changePasswordDescription")}</p>
          <label>
            {t("security.currentPassword")}
            <input
              aria-label={t("security.currentPassword")}
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </label>
          <label>
            {t("security.newPassword")}
            <input
              aria-label={t("security.newPassword")}
              type="password"
              autoComplete="new-password"
              minLength={12}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          <label>
            {t("security.confirmPassword")}
            <input
              aria-label={t("security.confirmPassword")}
              type="password"
              autoComplete="new-password"
              minLength={12}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
          </label>
          {enabled && (
            <label>
              {t("security.mfaCode")}
              <input
                aria-label={t("security.mfaCode")}
                autoComplete="one-time-code"
                value={passwordMfa}
                onChange={(e) => setPasswordMfa(e.target.value)}
              />
            </label>
          )}
          <button
            disabled={
              busy ||
              !currentPassword ||
              newPassword.length < 12 ||
              !confirmPassword ||
              (enabled === true && !passwordMfa)
            }
            onClick={() => void updatePassword()}
          >
            {busy ? t("security.updating") : t("security.changePassword")}
          </button>
        </article>
        <article className="card">
          <h2>{t("security.devices")}</h2>
          {sessions.length === 0 ? (
            <p>{t("security.noSessions")}</p>
          ) : (
            <ul>
              {sessions.map((item) => (
                <li key={item.id}>
                  <strong>
                    {item.current
                      ? t("security.thisDevice")
                      : t("security.otherDevice")}
                  </strong>{" "}
                  · {t("security.lastActive")}{" "}
                  {new Date(item.last_seen_at).toLocaleString(dateLocale)}{" "}
                  {!item.current && (
                    <button
                      disabled={busy}
                      onClick={() => void removeDevice(item.id)}
                    >
                      {t("security.signOutDevice")}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </article>
        <article className="card">
          <h2>{t("security.privacy")}</h2>
          <p>{t("security.privacyDescription")}</p>
          <label>
            {t("security.dataPassword")}
            <input
              aria-label={t("security.dataPassword")}
              type="password"
              autoComplete="current-password"
              value={sensitivePassword}
              onChange={(e) => setSensitivePassword(e.target.value)}
            />
          </label>
          {enabled && (
            <label>
              {t("security.mfaCode")}
              <input
                aria-label={t("security.mfaCode")}
                autoComplete="one-time-code"
                value={sensitiveMfa}
                onChange={(e) => setSensitiveMfa(e.target.value)}
              />
            </label>
          )}
          <button
            disabled={
              busy || !sensitivePassword || (enabled === true && !sensitiveMfa)
            }
            onClick={() => void exportData()}
          >
            {busy ? t("security.preparing") : t("security.downloadData")}
          </button>
          <hr />
          <h3>{t("security.deleteAccount")}</h3>
          <p>{t("security.deleteDescription")}</p>
          <label>
            {t("security.deletePrompt", { keyword: deleteKeyword })}
            <input
              aria-label={t("security.deleteConfirmation")}
              value={deletePhrase}
              onChange={(e) => setDeletePhrase(e.target.value)}
            />
          </label>
          <button
            disabled={
              busy ||
              !sensitivePassword ||
              deletePhrase !== deleteKeyword ||
              (enabled === true && !sensitiveMfa)
            }
            onClick={() => void removeAccount()}
          >
            {busy ? t("security.deleting") : t("security.deletePermanently")}
          </button>
        </article>
        <article className="card">
          <h2>{t("security.mfa")}</h2>
          {enabled === null ? (
            <p>{t("security.loadingSettings")}</p>
          ) : enabled ? (
            <>
              <p>{t("security.mfaEnabled", { count: remaining })}</p>
              <label>
                {t("security.authenticatorOrRecovery")}
                <input
                  aria-label={t("security.authenticatorOrRecovery")}
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </label>
              <div className="actions">
                <button disabled={busy || !code} onClick={() => void rotate()}>
                  {busy
                    ? t("security.processing")
                    : t("security.generateRecovery")}
                </button>
                <button disabled={busy || !code} onClick={() => void disable()}>
                  {busy ? t("security.processing") : t("security.disableMfa")}
                </button>
              </div>
            </>
          ) : secret ? (
            <>
              <p>{t("security.scanInstruction")}</p>
              <code style={{ display: "block", overflowWrap: "anywhere" }}>
                {uri}
              </code>
              <p>
                {t("security.manualKey")} <strong>{secret}</strong>
              </p>
              <label>
                {t("security.authenticatorCode")}
                <input
                  aria-label={t("security.authenticatorCode")}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                />
              </label>
              <button disabled={busy || !code} onClick={() => void confirm()}>
                {busy ? t("security.verifying") : t("security.enableMfa")}
              </button>
            </>
          ) : (
            <>
              <p>{t("security.mfaDisabled")}</p>
              <label>
                {t("security.currentPassword")}
                <input
                  aria-label={`${t("security.currentPassword")} (${t("security.mfa")})`}
                  type="password"
                  autoComplete="current-password"
                  value={mfaSetupPassword}
                  onChange={(e) => setMfaSetupPassword(e.target.value)}
                />
              </label>
              <button
                disabled={busy || !mfaSetupPassword}
                onClick={() => void setup()}
              >
                {busy ? t("security.preparing") : t("security.setupMfa")}
              </button>
            </>
          )}
          {codes.length > 0 && (
            <section className="card">
              <h2>{t("security.recoveryTitle")}</h2>
              <p>{t("security.recoveryDescription")}</p>
              <ul>
                {codes.map((value) => (
                  <li key={value}>
                    <code>{value}</code>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </article>
      </section>
    </main>
  );
}
