import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  getMatchReport,
  importJobScreenshot,
  importJobUrl,
  previewJobAnalysis,
  saveAnalyzedJob,
} from "../../services/jobApi";
import type { MatchReport } from "../../types/job";
import type { NavigationJob } from "../../types/dashboard";
import { PageFeedback } from "../../components/PageFeedback";
import { QuantInternshipReadinessPack } from "../../components/QuantInternshipReadinessPack";
import { useT } from "../../i18n/LanguageProvider";

export function JobAnalysisPage({
  onJobAnalyzed,
  onReturnToDashboard,
  onOpenResourcePlan,
  initialJob,
}: {
  onJobAnalyzed?: (job: NavigationJob) => void;
  onReturnToDashboard?: () => void;
  onOpenResourcePlan?: (job: NavigationJob) => void;
  initialJob?: NavigationJob;
}) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [description, setDescription] = useState("");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);

  const [report, setReport] = useState<MatchReport | null>(null);
  const [activeAction, setActiveAction] = useState<
    "loading-report" | "import-url" | "import-screenshot" | "analyze" | "save" | null
  >(null);
  const [error, setError] = useState("");
  const [decisionDismissed, setDecisionDismissed] = useState(false);

  const t = useT();

  // A role imported from Opportunity Radar has already been persisted and
  // analysed by the backend. Load its report rather than asking the user to
  // paste or analyse the same official post a second time.
  useEffect(() => {
    if (!initialJob?.id) return;
    let active = true;
    setActiveAction("loading-report");
    setError("");
    void getMatchReport(initialJob.id)
      .then((next) => {
        if (!active) return;
        setReport(next);
        setTitle(next.job.title);
        setCompany(next.job.company);
        setDescription(next.job.description);
      })
      .catch((reason) => {
        if (active)
          setError(
            reason instanceof Error ? reason.message : t("job.analyzing"),
          );
      })
      .finally(() => {
        if (active) setActiveAction(null);
      });
    return () => {
      active = false;
    };
  }, [initialJob?.id]);

  const applyDraft = (draft: {
    title: string;
    company: string;
    description: string;
    location: string;
    deadline: string;
    source_url: string;
  }) => {
    setTitle(draft.title);
    setCompany(draft.company);
    setDescription(draft.description);
  };

  const importUrl = async () => {
    setActiveAction("import-url");
    setError("");
    try {
      applyDraft(await importJobUrl(url));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("job.importing"));
    } finally {
      setActiveAction(null);
    }
  };

  const importScreenshot = async () => {
    if (!file || !consent) return;
    setActiveAction("import-screenshot");
    setError("");
    try {
      applyDraft(await importJobScreenshot(file, consent));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("job.recognizing"));
    } finally {
      setActiveAction(null);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setActiveAction("analyze");
    try {
      const preview = await previewJobAnalysis({
        title: title || "Untitled role",
        company,
        description,
      });
      setReport(preview);
      setDecisionDismissed(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("job.analyzing"));
    } finally {
      setActiveAction(null);
    }
  };

  const saveToWorkspace = async () => {
    if (!report) return;
    setActiveAction("save");
    setError("");
    try {
      const job = await saveAnalyzedJob({
        title: report.job.title,
        company: report.job.company,
        description: report.job.description,
        required_skills: report.job.required_skills,
        preferred_skills: report.job.preferred_skills,
        responsibilities: report.job.responsibilities,
        qualifications: report.job.qualifications,
      });
      setReport({ ...report, job });
      onJobAnalyzed?.({ id: job.id, title: job.title, company: job.company });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("job.workspaceSaveFailed"));
    } finally {
      setActiveAction(null);
    }
  };

  const isSaved = Boolean(report && report.job.id > 0);

  return (
    <main className="product-page job-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· JOB ANALYSIS</span>
          </p>
          <h1>{t("job.hero.title")}</h1>
          <p className="sub">{t("job.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-job" aria-hidden="true">
          <span>⌁</span>
        </div>
      </header>
      <section className="product-content job-workspace">
        <div className="job-input-stack">
          <div className="card import-panel">
            <p className="section-kicker">01 · IMPORT</p>
            <h2>{t("job.importTitle")}</h2>
            <label>
              {t("job.publicUrl")}
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://jobs.lever.co/..."
              />
            </label>
            <button
              disabled={activeAction !== null || !url.trim()}
              onClick={() => void importUrl()}
            >
              {activeAction === "import-url"
                ? t("job.importing")
                : t("job.importFromUrl")}
            </button>
            <p className="privacy-note">{t("job.hero.sub")}</p>
            <label>
              {t("job.screenshotLabel")}
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              {t("job.ocrConsent")}
            </label>
            <button
              disabled={activeAction !== null || !file || !consent}
              onClick={() => void importScreenshot()}
            >
              {activeAction === "import-screenshot"
                ? t("job.recognizing")
                : t("job.importFromScreenshot")}
            </button>
          </div>
          <form className="card analysis-form" onSubmit={submit}>
            <p className="section-kicker">02 · ANALYSE</p>
            <label>
              {t("job.field.title")}
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Quantitative Research Intern"
              />
            </label>
            <label>
              {t("job.field.company")}
              <input
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Company name"
              />
            </label>
            <label>
              {t("job.field.description")}
              <textarea
                required
                minLength={20}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("job.descPlaceholder")}
              />
            </label>
            <button
              disabled={activeAction !== null || description.trim().length < 20}
            >
              {activeAction === "analyze" ? t("job.analyzing") : t("job.analyze")}
            </button>
          </form>
        </div>
        {error && <PageFeedback kind="error" message={error} />}
        {report && (
          <>
            <PageFeedback
              kind={isSaved ? "success" : "info"}
              message={t(isSaved ? "job.analyzedSaved" : "job.previewReady")}
              {...(isSaved
                ? {
                    actionLabel: t("profile.backToDashboard"),
                    onAction: onReturnToDashboard,
                  }
                : {})}
            />
            {!isSaved && !decisionDismissed && (
              <section className="card job-workspace-decision">
                <div>
                  <p className="section-kicker">03 · DECIDE</p>
                  <h2>{t("job.workspaceDecisionTitle")}</h2>
                  <p>{t("job.workspaceDecisionSub")}</p>
                </div>
                <div className="job-workspace-decision-actions">
                  <button
                    disabled={activeAction !== null}
                    onClick={() => void saveToWorkspace()}
                  >
                    {activeAction === "save"
                      ? t("job.workspaceSaving")
                      : t("job.addToWorkspace")}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    disabled={activeAction !== null}
                    onClick={() => setDecisionDismissed(true)}
                  >
                    {t("job.keepPreviewOnly")}
                  </button>
                </div>
              </section>
            )}
            {!isSaved && decisionDismissed && (
              <PageFeedback kind="info" message={t("job.previewNotSaved")} />
            )}
            <MatchResult
              report={report}
              canGeneratePlan={isSaved}
              onOpenResourcePlan={onOpenResourcePlan}
            />
          </>
        )}
      </section>
    </main>
  );
}

function MatchResult({
  report,
  canGeneratePlan,
  onOpenResourcePlan,
}: {
  report: MatchReport;
  canGeneratePlan: boolean;
  onOpenResourcePlan?: (job: NavigationJob) => void;
}) {
  const t = useT();

  const requiredMissing =
    report.missing_required_skills ?? report.missing_skills;

  const preferredMissing = report.missing_preferred_skills ?? [];

  const matchedRequired =
    report.matched_required_skills ?? report.matched_skills;

  const matchedPreferred = report.matched_preferred_skills ?? [];

  const labels: Record<string, string> = {
    required_skill_match: t("ai.feature.job_match"),
    preferred_skill_match: t("job.preferredSkills"),
    experience_relevance: t("job.hero.title"),
    quantified_evidence: t("shared.sources"),
    education_background: t("builder.exportTitle"),
    qualification_coverage: t("job.qualifications"),
  };

  return (
    <div className="report">
      <div className="score">
        <span>{t("job.matchScore")}</span>
        <strong>{report.overall_score}</strong>
        <small>/ 100</small>
      </div>
      {report.warnings?.map((warning) => (
        <p className="warning" key={warning}>
          {warning}
        </p>
      ))}
      <div className="card">
        <h2>
          {report.job.title}
          {report.job.company ? ` · ${report.job.company}` : ""}
        </h2>
        <h3>{t("job.requiredSkills")}</h3>
        <div className="tags">
          {report.job.required_skills.length ? (
            report.job.required_skills.map((skill) => (
              <span key={skill}>{skill}</span>
            ))
          ) : (
            <p>{t("job.noRequired")}</p>
          )}
        </div>
        <h3>{t("job.matchedRequired")}</h3>
        <div className="tags">
          {matchedRequired.length ? (
            matchedRequired.map((skill) => <span key={skill}>{skill}</span>)
          ) : (
            <p>{t("job.noMatchedRequired")}</p>
          )}
        </div>
        <h3>{t("job.requiredGap")}</h3>
        <div className="tags">
          {requiredMissing.length ? (
            requiredMissing.map((skill) => (
              <span className="missing" key={skill}>
                {skill}
              </span>
            ))
          ) : (
            <p>{t("job.noRequiredGap")}</p>
          )}
        </div>

        {report.job.preferred_skills.length > 0 && (
          <>
            <h3>{t("job.preferredSkills")}</h3>
            <div className="tags">
              {report.job.preferred_skills.map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
            <h3>{t("job.matchedPreferred")}</h3>
            <div className="tags">
              {matchedPreferred.length ? (
                matchedPreferred.map((skill) => (
                  <span key={skill}>{skill}</span>
                ))
              ) : (
                <p>{t("job.noMatchedPreferred")}</p>
              )}
            </div>
            <h3>{t("job.preferredGap")}</h3>
            <div className="tags">
              {preferredMissing.length ? (
                preferredMissing.map((skill) => (
                  <span className="missing" key={skill}>
                    {skill}
                  </span>
                ))
              ) : (
                <p>{t("job.noPreferredGap")}</p>
              )}
            </div>
          </>
        )}

        {report.job.responsibilities.length > 0 && (
          <>
            <h3>{t("job.responsibilities")}</h3>
            <ul>
              {report.job.responsibilities.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}

        {report.job.qualifications.length > 0 && (
          <>
            <h3>{t("job.qualifications")}</h3>
            <ul>
              {report.job.qualifications.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </>
        )}
      </div>

      {report.score_breakdown &&
        Object.keys(report.score_breakdown).length > 0 && (
          <div className="card">
            <h2>{t("job.scoreBreakdown")}</h2>
            <ul>
              {Object.entries(report.score_breakdown).map(([key, value]) => (
                <li key={key}>
                  {t("job.scoreUnit", { label: labels[key] || key, value })}
                </li>
              ))}
            </ul>
          </div>
        )}
      <div className="card">
        <h2>{t("job.evidence")}</h2>
        {report.evidence.length ? (
          <ul>
            {report.evidence.map((item, i) => (
              <li key={`${item.experience_id}-${i}`}>
                <strong>{item.requirement}</strong> · {item.experience_title}
                <br />
                <small>{item.evidence}</small>
              </li>
            ))}
          </ul>
        ) : (
          <p>{t("job.confirmFirst")}</p>
        )}
      </div>
      <div className="card proof-map">
        <p className="section-kicker">APPLYEASE · PROOF MAP</p>
        <h2>{t("proof.title")}</h2>
        <p className="privacy-note">{t("proof.sub")}</p>
        <ul>
          {[...report.job.required_skills, ...report.job.preferred_skills].map(
            (requirement) => {
              const evidence = report.evidence.find(
                (item) => item.requirement === requirement,
              );
              return (
                <li
                  className={evidence ? "proof-supported" : "proof-gap"}
                  key={requirement}
                >
                  <strong>{requirement}</strong>
                  {evidence ? (
                    <span>
                      {t("proof.supported", {
                        title: evidence.experience_title,
                      })}
                    </span>
                  ) : (
                    <span>{t("proof.gap")}</span>
                  )}
                </li>
              );
            },
          )}
        </ul>
        {canGeneratePlan && (requiredMissing.length || preferredMissing.length) > 0 && (
          <button
            type="button"
            onClick={() =>
              onOpenResourcePlan?.({
                id: report.job.id,
                title: report.job.title,
                company: report.job.company,
              })
            }
          >
            {t("proof.planAction")}
          </button>
        )}
      </div>
      <QuantInternshipReadinessPack report={report} />
    </div>
  );
}
