import { useEffect, useRef, useState } from "react";
import {
  askAdvisor,
  clearAdvisorHistory,
  getAdvisorHistory,
} from "../services/advisorApi";
import type { AdvisorMessage } from "../types/advisor";
import type { NavigationJob } from "../types/dashboard";
import { useI18n, useT } from "../i18n/LanguageProvider";

const opening = (t: (key: string) => string): AdvisorMessage => ({
  role: "assistant",
  content: t("advisor.welcome"),
});

type AdvisorAssistantProps = {
  activePage: string;
  activeJob?: NavigationJob;
};

export function AdvisorAssistant({ activePage, activeJob }: AdvisorAssistantProps) {
  const t = useT();
  const { language } = useI18n();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failedQuestion, setFailedQuestion] = useState("");
  const [messages, setMessages] = useState<AdvisorMessage[]>(() => [
    opening(t),
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  // Keep the untouched greeting in sync with the selected interface language.
  // Once a conversation starts we preserve its history rather than silently
  // replacing messages the user may still be reading.
  useEffect(() => {
    setMessages((current) =>
      current.length === 1 && current[0].role === "assistant"
        ? [opening(t)]
        : current,
    );
  }, [language]);
  useEffect(() => {
    let active = true;
    void getAdvisorHistory()
      .then((history) => {
        if (active && history.length) setMessages(history);
      })
      // The assistant stays available in an empty state if history cannot be
      // loaded; a failed history fetch must not block a new question.
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);
  const clear = async () => {
    if (busy) return;
    setBusy(true);
    setError("");
    setFailedQuestion("");
    try {
      await clearAdvisorHistory();
      setMessages([opening(t)]);
      setText("");
    } catch {
      setError(t("advisor.error"));
    } finally {
      setBusy(false);
    }
  };
  const send = async (value = text) => {
    const question = value.trim();
    if (!question || busy) return;
    const userMessage: AdvisorMessage = { role: "user", content: question };
    const previous = messages[messages.length - 1];
    const history =
      previous?.role === "user" && previous.content === question
        ? messages
        : [...messages, userMessage];
    setMessages(history);
    setText("");
    setError("");
    setFailedQuestion("");
    setBusy(true);
    try {
      const reply = await askAdvisor(question, history, language, {
        activePage,
        activeJobId: activeJob?.id,
      });
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: reply.answer,
          sources: reply.sources,
          suggested_prompts: reply.suggested_prompts,
          used_fallback: reply.used_fallback,
        },
      ]);
    } catch {
      setError(t("advisor.error"));
      setFailedQuestion(question);
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside
      className={`advisor-shell ${open ? "is-open" : ""}`}
      aria-label={t("advisor.title")}
    >
      {open && (
        <section className="advisor-panel">
          <header className="advisor-header">
            <div className="advisor-avatar large" aria-hidden="true">
              <span className="avatar-ring" />
              <span className="avatar-face">
                <i />
                <i />
                <b />
              </span>
            </div>
            <div>
              <p>{t("advisor.eyebrow")}</p>
              <h2>{t("advisor.title")}</h2>
              <small>
                <i /> {t("advisor.online")}
              </small>
            </div>
            <button
              className="advisor-close"
              type="button"
              aria-label={t("advisor.close")}
              onClick={() => setOpen(false)}
            >
              ×
            </button>
          </header>
          <p className="advisor-context">{t("advisor.context")}</p>
          <p className="advisor-live-context">
            {t("advisor.activeContext", {
              context: activeJob
                ? `${activeJob.company} · ${activeJob.title}`
                : t("advisor.currentWorkspace"),
            })}
          </p>
          <div className="advisor-messages" aria-live="polite">
            {messages.map((message, index) => (
              <article
                className={`advisor-message ${message.role}`}
                key={`${message.role}-${index}`}
              >
                <p>{message.content}</p>
                {message.used_fallback && (
                  <small className="advisor-fallback">
                    {t("advisor.fallback")}
                  </small>
                )}
                {message.sources?.length ? (
                  <div className="advisor-sources">
                    <small>{t("advisor.sources")}</small>
                    {message.sources.map((source) => (
                      <span key={source}>⌁ {source}</span>
                    ))}
                  </div>
                ) : null}
                {message.suggested_prompts?.length ? (
                  <div className="advisor-suggestions">
                    {message.suggested_prompts.map((prompt) => (
                      <button
                        type="button"
                        key={prompt}
                        onClick={() => void send(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                  </div>
                ) : null}
              </article>
            ))}
            {busy && (
              <article className="advisor-message assistant advisor-typing">
                <span />
                <span />
                <span />
              </article>
            )}
            <div ref={endRef} />
          </div>
          {error && (
            <p className="advisor-error" role="alert">
              {error}
              {failedQuestion ? (
                <button type="button" onClick={() => void send(failedQuestion)}>
                  {t("advisor.retry")}
                </button>
              ) : null}
            </p>
          )}
          <form
            className="advisor-composer"
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            <textarea
              aria-label={t("advisor.placeholder")}
              value={text}
              maxLength={2000}
              onChange={(event) => setText(event.target.value)}
              placeholder={t("advisor.placeholder")}
            />
            <div>
              <button
                type="button"
                className="advisor-clear"
                disabled={busy}
                onClick={() => void clear()}
              >
                {t("advisor.clear")}
              </button>
              <button type="submit" disabled={!text.trim() || busy}>
                {t("advisor.send")} <span aria-hidden="true">↑</span>
              </button>
            </div>
          </form>
        </section>
      )}
      <button
        className="advisor-launcher"
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span className="advisor-avatar" aria-hidden="true">
          <span className="avatar-ring" />
          <span className="avatar-face">
            <i />
            <i />
            <b />
          </span>
        </span>
        <span className="advisor-launcher-label">
          <strong>{t("advisor.title")}</strong>
          <small>{t("advisor.launcher")}</small>
        </span>
        {!open && <em>✦</em>}
      </button>
    </aside>
  );
}
