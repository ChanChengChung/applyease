import { useEffect, useState } from "react";
import { ApplicationQuestionCard } from "../../components/ApplicationQuestionCard";
import { PageFeedback } from "../../components/PageFeedback";
import {
  detectQuestions,
  detectScreenshot,
  getBatchGenerationTask,
  getLatestApplication,
  getSavedAnswers,
  generateAllAnswers,
  generateQuestionAnswer,
  updateQuestionAnswer,
} from "../../services/applicationApi";
import type {
  AnswerTemplate,
  Application,
  ApplicationQuestion,
  GeneratedAnswer,
} from "../../types/application";
import { useI18n } from "../../i18n/LanguageProvider";
import { listJobs } from "../../services/jobApi";
import type { Job } from "../../types/job";

// Built-in fixture so the form copilot can be demonstrated without a live
// external careers page or the browser extension. Mirrors demo/polymer_application_questions.txt.
const DEMO_QUESTIONS = `Full name *
Email address *
Are you legally authorized to work in Hong Kong? *
Why are you interested in Polymer Capital and this AI internship? Maximum 150 words *
Describe a project where you used AI to solve a real-world problem. Maximum 300 words *
What technical skill would you most like to improve during the internship? Maximum 100 words *`;

export function ApplicationFormPage({
  initialJobId,
  onJobSelected,
  onReturnToDashboard,
}: {
  initialJobId?: number;
  onJobSelected?: (job: { id: number; title: string; company: string }) => void;
  onReturnToDashboard?: () => void;
}) {
  const [jobId, setJobId] = useState(initialJobId ? String(initialJobId) : "");
  const [jobs, setJobs] = useState<Job[]>([]);

  const [rawText, setRawText] = useState("");
  const [application, setApplication] = useState<Application | null>(null);
  const [screenshotConsent, setScreenshotConsent] = useState(false);

  const [answers, setAnswers] = useState<Record<number, GeneratedAnswer>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [batchTemplate, setBatchTemplate] = useState<AnswerTemplate>("auto");
  const [batchProgress, setBatchProgress] = useState<{ completed: number; total: number } | null>(null);
  const [questionTemplates, setQuestionTemplates] = useState<
    Record<number, AnswerTemplate>
  >({});

  const { language, t } = useI18n();
  useEffect(() => {
    void listJobs()
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);
  useEffect(() => {
    if (initialJobId) setJobId(String(initialJobId));
  }, [initialJobId]);
  useEffect(() => {
    const id = Number(jobId);
    if (!Number.isInteger(id) || id <= 0) {
      setApplication(null);
      setAnswers({});
      return;
    }
    let active = true;
    void getLatestApplication(id)
      .then(async (saved) => {
        const savedAnswers = await getSavedAnswers(saved.id);
        if (!active) return;
        setApplication(saved);
        setRawText(saved.raw_text);
        setAnswers(
          Object.fromEntries(
            savedAnswers.map((answer) => [answer.question_id, answer]),
          ),
        );
      })
      .catch(() => {
        if (active) {
          setApplication(null);
          setAnswers({});
        }
      });
    return () => {
      active = false;
    };
  }, [jobId]);

  const detect = async (event: React.FormEvent, text = rawText) => {
    event.preventDefault();
    const id = Number(jobId);
    if (!Number.isInteger(id) || id <= 0) {
      setError(t("form.invalidJobId"));
      return;
    }
    setError("");
    setBusy(true);
    try {
      setApplication(await detectQuestions(id, text));
      setAnswers({});
      setQuestionTemplates({});
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.detectFailed"));
    } finally {
      setBusy(false);
    }
  };

  const detectImage = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.currentTarget.value = "";
    const id = Number(jobId);
    if (!file) return;
    if (!Number.isInteger(id) || id <= 0) {
      setError(t("form.jobIdFirst"));
      return;
    }
    if (!screenshotConsent) {
      setError(t("form.ocrConsentRequired"));
      return;
    }
    setError("");
    setBusy(true);
    try {
      setApplication(await detectScreenshot(id, file, screenshotConsent));
      setAnswers({});
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.screenshotFailed"));
    } finally {
      setBusy(false);
    }
  };

  const answer = async (question: ApplicationQuestion) => {
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      const result = await generateQuestionAnswer(
        application.id,
        question.id,
        questionTemplates[question.id] || "auto",
        language,
      );
      setAnswers((previous) => ({ ...previous, [question.id]: result }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.answerFailed"));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const save = async (question: ApplicationQuestion, text: string) => {
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      const result = await updateQuestionAnswer(
        application.id,
        question.id,
        text,
      );
      setAnswers((previous) => ({ ...previous, [question.id]: result }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.saveFailed"));
      throw e;
    } finally {
      setBusy(false);
    }
  };

  const answerAll = async (regenerate = false) => {
    if (!application) return;
    setBusy(true);
    setError("");
    try {
      const task = await generateAllAnswers(
        application.id,
        regenerate,
        batchTemplate,
        language,
      );
      setBatchProgress({ completed: task.completed, total: task.total });
      let latest = task;
      while (latest.status === "queued" || latest.status === "running") {
        await new Promise((resolve) => window.setTimeout(resolve, 600));
        latest = await getBatchGenerationTask(latest.task_id);
        setBatchProgress({ completed: latest.completed, total: latest.total });
      }
      setAnswers(
        Object.fromEntries(
          latest.results.map((result) => [result.question_id, result]),
        ),
      );
      if (latest.status === "failed" || latest.errors.length) {
        setError(latest.errors.join(" ") || t("form.batchFailed"));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("form.batchFailed"));
    } finally {
      setBatchProgress(null);
      setBusy(false);
    }
  };

  const complete = Boolean(
    application &&
    application.questions
      .filter((question) => question.required)
      .every((question) => Boolean(answers[question.id]?.answer.trim())),
  );

  return (
    <main className="product-page form-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· APPLICATION FORM COPILOT</span>
          </p>
          <h1>{t("form.hero.title")}</h1>
          <p className="sub">{t("form.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-form" aria-hidden="true">
          <span>↗</span>
        </div>
      </header>
      <section className="product-content">
        {complete && (
          <PageFeedback
            kind="success"
            message={t("form.allAnswered")}
            actionLabel={t("profile.backToDashboard")}
            onAction={onReturnToDashboard}
          />
        )}
        <form className="card form-intake" aria-busy={busy} onSubmit={detect}>
          <div className="form-intake-primary">
            <p className="section-kicker">01 · FIELD CAPTURE</p>
            <label>
              {t("resource.target")}
              <select
                aria-label={t("resource.target")}
                value={jobId}
                onChange={(e) => {
                  setJobId(e.target.value);
                  const job = jobs.find((item) => item.id === Number(e.target.value));
                  if (job) onJobSelected?.({ id: job.id, title: job.title, company: job.company });
                }}
              >
                <option value="">{t("resource.selectTarget")}</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.company} · {job.title}
                  </option>
                ))}
              </select>
            </label>
            {!jobs.length && (
              <p className="privacy-note">{t("resource.noTargets")}</p>
            )}
            <button
              type="button"
              className="text-action"
              disabled={busy || !jobId}
              onClick={() => {
                setRawText(DEMO_QUESTIONS);
                void detect(
                  {
                    preventDefault: () => undefined,
                  } as React.FormEvent,
                  DEMO_QUESTIONS,
                );
              }}
            >
              {t("form.loadDemo")}
            </button>
            <label>
              {t("form.pageText")}
              <textarea
                required
                minLength={10}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                placeholder={t("form.pageTextPlaceholder")}
              />
            </label>
            <button disabled={busy || !jobId || rawText.trim().length < 10}>
              {busy ? t("form.processing") : t("form.detect")}
            </button>
          </div>
          <aside className="form-ocr-panel">
            <div className="form-ocr-heading">
              <span aria-hidden="true">⌁</span>
              <div>
                <strong>{t("form.screenshot")}</strong>
                <p>{t("form.ocrConsent")}</p>
              </div>
            </div>
            <label className="ocr-consent">
              <input
                type="checkbox"
                checked={screenshotConsent}
                onChange={(event) => setScreenshotConsent(event.target.checked)}
              />
              <span>{t("form.ocrConsent")}</span>
            </label>
            <label className="file-drop">
              <span>{t("form.screenshot")}</span>
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={busy}
                onChange={(event) => void detectImage(event)}
              />
            </label>
          </aside>
        </form>

        {error && <PageFeedback kind="error" message={error} />}

        {application && (
          <div className="card">
            <div className="card-header">
              <h2>
                {t("form.fieldsDetected", { n: application.questions.length })}
              </h2>
              <div className="actions">
                <label>
                  {t("form.template")}
                  <select
                    aria-label={t("form.batchTemplate")}
                    value={batchTemplate}
                    onChange={(event) =>
                      setBatchTemplate(event.target.value as AnswerTemplate)
                    }
                  >
                    <option value="auto">{t("template.auto")}</option>
                    <option value="concise_50">
                      {t("template.concise50")}
                    </option>
                    <option value="standard_150">
                      {t("template.standard150")}
                    </option>
                    <option value="detailed_300">
                      {t("template.detailed300")}
                    </option>
                    <option value="star">{t("template.star")}</option>
                  </select>
                </label>
                <button disabled={busy} onClick={() => void answerAll(false)}>
                  {t("form.genAll")}
                </button>
                <button disabled={busy} onClick={() => void answerAll(true)}>
                  {t("form.regenAll")}
                </button>
              </div>
            </div>
            {batchProgress && (
              <p className="privacy-note" role="status">
                {batchProgress.completed}/{batchProgress.total} {t("form.processing")}
              </p>
            )}
            {application.questions.map((question) => (
              <ApplicationQuestionCard
                key={question.id}
                question={question}
                answer={answers[question.id]}
                busy={busy}
                template={questionTemplates[question.id] || "auto"}
                onTemplateChange={(template) =>
                  setQuestionTemplates((previous) => ({
                    ...previous,
                    [question.id]: template,
                  }))
                }
                onGenerate={() => answer(question)}
                onSave={(text) => save(question, text)}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
