import { useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import {
  askAdvisor,
  clearAdvisorHistory,
  getAdvisorHistory,
} from "../services/advisorApi";
import type { AdvisorAction, AdvisorMessage } from "../types/advisor";
import type { NavigationJob } from "../types/dashboard";
import { useI18n, useT } from "../i18n/LanguageProvider";

const opening = (t: (key: string) => string): AdvisorMessage => ({
  role: "assistant",
  content: t("advisor.welcome"),
});

type AdvisorAssistantProps = {
  activePage: string;
  activeJob?: NavigationJob;
  onNavigate?: (target: AdvisorAction["target_page"], targetId?: number | null) => void;
};

const quickPrompts = (language: string, page: string): string[] => {
  const fallback = language === "en"
    ? ["Can you help me decide what to do next?", "Which part of my evidence should we look at?", "What is the most important gap to close?"]
    : language === "zh-CN"
      ? ["你能帮我一起决定下一步吗？", "我们先看看哪条经历最合适？", "现在最值得补上的缺口是什么？"]
      : ["你能幫我一起決定下一步嗎？", "我們先看看哪項經歷最合適？", "現在最值得補上的缺口是什麼？"];
  const prompts: Record<string, string[]> = language === "en" ? {
    profile: ["Which confirmed experience would you lead with?", "Can we check what still needs confirmation?", "What is one useful improvement for my evidence bank?"],
    jobs: ["What would you prepare first for this role?", "Does this role look ready to add to my tracker?", "Which requirement should I investigate more carefully?"],
    opportunities: ["Which of these roles fits my evidence best?", "What should I verify before I apply?", "Can you help me compare these opportunities?"],
    builder: ["Which sentence in my resume feels too strong?", "How can we tailor this material without overstating anything?", "What would you change before I export it?"],
    form: ["Which question would be easiest to answer first?", "Can my confirmed evidence support this answer?", "What should I double-check before submitting?"],
    resources: ["What would be a realistic thing for me to learn next?", "Which gap matters most for my goal right now?", "How could I turn this resource into a small project?"],
    tracker: ["Which deadline should I deal with first?", "What follow-up would make sense next?", "How can I practise for this interview?"],
  } : language === "zh-CN" ? {
    profile: ["你觉得我应该先突出哪段已确认经历？", "我们可以一起看看还有哪些经历待确认吗？", "经历库现在最值得补强什么？"],
    jobs: ["这个职位你建议我先准备什么？", "它现在适合加入申请追踪吗？", "哪个要求值得我再仔细核对？"],
    opportunities: ["这些机会里哪个最适合我的经历？", "申请前我还应该确认什么？", "你能帮我比较一下这些职位吗？"],
    builder: ["简历里哪句话可能说得太满？", "怎样定制材料才能既有针对性又不夸大？", "导出前你建议我改哪里？"],
    form: ["哪道申请题最适合先回答？", "我的已确认经历能支持这道题吗？", "提交前还有什么需要仔细检查？"],
    resources: ["结合我的情况，下一步学什么比较现实？", "现在最值得补上的能力缺口是哪一个？", "怎样把这个资源变成一个小项目？"],
    tracker: ["我应该先处理哪个截止日期？", "下一步跟进做什么比较合适？", "你能陪我练习这场面试吗？"],
  } : {
    profile: ["你覺得我應該先突出哪項已確認經歷？", "我們可以一起看看還有哪些經歷待確認嗎？", "經歷庫現在最值得補強什麼？"],
    jobs: ["這個職位你建議我先準備什麼？", "它現在適合加入申請追蹤嗎？", "哪個要求值得我再仔細核對？"],
    opportunities: ["這些機會中哪個最適合我的經歷？", "申請前我還應該確認什麼？", "你能幫我比較一下這些職位嗎？"],
    builder: ["履歷裡哪句話可能說得太滿？", "怎樣客製材料才能既有針對性又不誇大？", "匯出前你建議我改哪裡？"],
    form: ["哪道申請題最適合先回答？", "我的已確認經歷能支持這道題嗎？", "提交前還有什麼需要仔細檢查？"],
    resources: ["結合我的情況，下一步學什麼比較現實？", "現在最值得補上的能力缺口是哪一個？", "怎樣把這個資源變成一個小專案？"],
    tracker: ["我應該先處理哪個截止日期？", "下一步跟進做什麼比較合適？", "你能陪我練習這場面試嗎？"],
  };
  return prompts[page] || fallback;
};

export function AdvisorAssistant({ activePage, activeJob, onNavigate }: AdvisorAssistantProps) {
  const t = useT();
  const { language } = useI18n();
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const [dragging, setDragging] = useState(false);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [failedQuestion, setFailedQuestion] = useState("");
  const [messages, setMessages] = useState<AdvisorMessage[]>(() => [
    opening(t),
  ]);
  const endRef = useRef<HTMLDivElement>(null);
  const shellRef = useRef<HTMLElement>(null);
  const dragMovedRef = useRef(false);
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
          summary: reply.summary,
          sources: reply.sources,
          evidence: reply.evidence,
          gaps: reply.gaps,
          next_actions: reply.next_actions,
          suggested_prompts: reply.suggested_prompts,
          used_fallback: reply.used_fallback,
          mode: reply.mode,
        },
      ]);
    } catch {
      setError(t("advisor.error"));
      setFailedQuestion(question);
    } finally {
      setBusy(false);
    }
  };
  const startDrag = (event: ReactPointerEvent<HTMLElement>) => {
    // Controls inside the header must keep their normal click behaviour.
    if (
      event.currentTarget.classList.contains("advisor-header") &&
      (event.target as HTMLElement).closest("button")
    ) return;
    const rect = shellRef.current?.getBoundingClientRect();
    if (!rect) return;
    const offsetX = event.clientX - rect.left;
    const offsetY = event.clientY - rect.top;
    const startX = event.clientX;
    const startY = event.clientY;
    dragMovedRef.current = false;
    setDragging(true);
    if (typeof event.currentTarget.setPointerCapture === "function") {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    const move = (moveEvent: PointerEvent) => {
      if (Math.hypot(moveEvent.clientX - startX, moveEvent.clientY - startY) > 4) {
        dragMovedRef.current = true;
      }
      const left = Math.min(Math.max(8, moveEvent.clientX - offsetX), Math.max(8, window.innerWidth - rect.width - 8));
      const top = Math.min(Math.max(8, moveEvent.clientY - offsetY), Math.max(8, window.innerHeight - rect.height - 8));
      setPosition({ left, top });
    };
    const stop = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", stop);
      window.removeEventListener("pointercancel", stop);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", stop);
    window.addEventListener("pointercancel", stop);
  };
  return (
    <aside
      ref={shellRef}
      className={`advisor-shell ${open ? "is-open" : ""} ${dragging ? "is-dragging" : ""}`}
      aria-label={t("advisor.title")}
      style={position ? { left: position.left, top: position.top, right: "auto", bottom: "auto" } : undefined}
    >
      {open && (
        <section className="advisor-panel">
          <header className="advisor-header" onPointerDown={startDrag} title={t("advisor.dragHint")}>
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
          <div className="advisor-quick-prompts" aria-label={t("advisor.quickPrompts")}>
            {quickPrompts(language, activePage).map((prompt) => (
              <button type="button" key={prompt} disabled={busy} onClick={() => void send(prompt)}>
                {prompt}
              </button>
            ))}
          </div>
          <div className="advisor-messages" aria-live="polite">
            {messages.map((message, index) => (
              <article
                className={`advisor-message ${message.role}`}
                key={`${message.role}-${index}`}
              >
                {message.summary && message.summary !== message.content ? (
                  <p className="advisor-summary">{message.summary}</p>
                ) : null}
                <p>{message.content}</p>
                {message.used_fallback && (
                  <small className="advisor-fallback">
                    {t("advisor.fallback")}
                  </small>
                )}
                {message.mode === "ai" && !message.used_fallback ? (
                  <small className="advisor-mode">{t("advisor.aiGrounded")}</small>
                ) : null}
                {message.evidence?.length ? (
                  <div className="advisor-evidence">
                    <small>{t("advisor.evidence")}</small>
                    {message.evidence.map((item) => (
                      <div className="advisor-evidence-item" key={`${item.type}-${item.id}-${item.label}`}>
                        {item.target_page && onNavigate ? (
                          <button type="button" onClick={() => onNavigate(item.target_page!, item.id)}>
                            {item.label}
                          </button>
                        ) : <strong>{item.label}</strong>}
                        {item.detail ? <span>{item.detail}</span> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
                {message.gaps?.length ? (
                  <div className="advisor-gaps">
                    <small>{t("advisor.gaps")}</small>
                    {message.gaps.map((gap) => <span key={gap}>• {gap}</span>)}
                  </div>
                ) : null}
                {message.next_actions?.length ? (
                  <div className="advisor-actions">
                    <small>{t("advisor.nextActions")}</small>
                    {message.next_actions.map((action) => (
                      <button key={`${action.target_page}-${action.label}`} type="button" onClick={() => onNavigate?.(action.target_page, action.target_id)}>
                        {action.label} →
                      </button>
                    ))}
                  </div>
                ) : null}
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
        onPointerDown={startDrag}
        onClick={() => {
          // A pointer release after moving the launcher is a drag, not an
          // instruction to open the chat. Reset the one-shot guard here.
          if (dragMovedRef.current) {
            dragMovedRef.current = false;
            return;
          }
          setOpen((value) => !value);
        }}
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
