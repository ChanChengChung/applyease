import { useEffect, useState } from "react";
import type {
  AnswerTemplate,
  ApplicationQuestion,
  GeneratedAnswer,
} from "../types/application";
import { useT } from "../i18n/LanguageProvider";

export function ApplicationQuestionCard({
  question,
  answer,
  busy,
  template = "auto",
  onTemplateChange = () => {},
  onGenerate,
  onSave,
}: {
  question: ApplicationQuestion;
  answer?: GeneratedAnswer;
  busy: boolean;
  template?: AnswerTemplate;
  onTemplateChange?: (template: AnswerTemplate) => void;
  onGenerate: () => Promise<void>;
  onSave: (text: string) => Promise<void>;
}) {
  const metadata = question.answer?.metadata || {};

  const manual = Boolean(metadata.requires_user_input);

  const [draft, setDraft] = useState(answer?.answer || "");

  const [error, setError] = useState("");

  const [copied, setCopied] = useState(false);

  const t = useT();

  useEffect(() => {
    setDraft(answer?.answer || "");
    setError("");
  }, [answer?.answer, question.id]);

  const save = async () => {
    setError("");

    try {
      await onSave(draft.trim());
    } catch (e) {
      setError(e instanceof Error ? e.message : t("shared.saveFailed"));
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(draft);
      setCopied(true);
    } catch {
      setError(t("shared.copyFailed"));
    }
  };

  const wordCount = draft.trim() ? draft.trim().split(/\s+/).length : 0;
  return (
    <article className="question">
      <p>
        <strong>{question.question}</strong>
      </p>
      <small>
        {t("shared.questionType", { type: question.question_type })} ·{" "}
        {question.required ? t("shared.required") : t("shared.optional")} ·{" "}
        {metadata.max_words
          ? t("shared.maxWords", { n: metadata.max_words })
          : t("shared.maxChars", { n: question.max_characters })}
      </small>
      {metadata.sensitive && <p className="error">{t("shared.sensitive")}</p>}
      {manual ? (
        <p>{t("shared.fillYourself")}</p>
      ) : (
        <div className="actions">
          <label>
            {t("form.template")}
            <select
              aria-label={`${t("form.template")}：${question.question}`}
              disabled={busy}
              value={template}
              onChange={(event) =>
                onTemplateChange(event.target.value as AnswerTemplate)
              }
            >
              <option value="auto">{t("template.auto")}</option>
              <option value="concise_50">{t("template.concise50")}</option>
              <option value="standard_150">{t("template.standard150")}</option>
              <option value="detailed_300">{t("template.detailed300")}</option>
              <option value="star">{t("template.star")}</option>
            </select>
          </label>
          <button disabled={busy} onClick={() => void onGenerate()}>
            {answer ? t("shared.regenerate") : t("shared.generate")}
          </button>
        </div>
      )}
      {!manual && answer?.recommended_template && (
        <small>
          {t("template.recommended", {
            template: t(`template.${answer.recommended_template}`),
          })}
          {answer.template
            ? ` · ${t("template.used", { template: t(`template.${answer.template}`) })}`
            : ""}
        </small>
      )}
      {(manual || answer) && (
        <>
          <label>
            {manual ? t("shared.yourAnswer") : t("shared.editAnswer")}
            <textarea
              aria-label={`${t("shared.yourAnswer")}：${question.question}`}
              value={draft}
              maxLength={question.max_characters}
              onChange={(event) => {
                setDraft(event.target.value);
                setCopied(false);
              }}
            />
          </label>
          <small>
            {t("shared.charCount", { n: draft.length })}
            {question.max_characters ? `/${question.max_characters}` : ""}
            {metadata.max_words
              ? ` · ${t("shared.words", { n: wordCount, max: metadata.max_words })}`
              : ""}
          </small>
          <div className="actions">
            <button
              disabled={
                busy ||
                !draft.trim() ||
                draft === answer?.answer ||
                Boolean(metadata.max_words && wordCount > metadata.max_words)
              }
              onClick={() => void save()}
            >
              {t("shared.saveAnswer")}
            </button>
            {draft && (
              <button onClick={() => void copy()}>
                {copied ? t("shared.copied") : t("shared.copyAnswer")}
              </button>
            )}
          </div>
        </>
      )}
      {answer?.warnings.map((warning) => (
        <p className="error" key={warning}>
          {warning}
        </p>
      ))}
      {answer?.structure_warnings?.map((warning) => (
        <p className="error" key={warning}>
          {warning}
        </p>
      ))}
      {answer?.sources.length ? (
        <details>
          <summary>{t("shared.factSources")}</summary>
          <ul>
            {answer.sources.map((source, index) => (
              <li key={`${source.experience_id}-${index}`}>
                <strong>{source.experience_title}</strong>
                {source.claim && (
                  <>
                    <br />
                    {t("shared.claim", { claim: source.claim })}
                  </>
                )}
                <br />
                <small>{t("shared.evidence", { text: source.text })}</small>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </article>
  );
}
