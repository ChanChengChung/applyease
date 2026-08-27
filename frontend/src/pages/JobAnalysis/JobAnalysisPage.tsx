import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  getMatchReport,
  importJobScreenshot,
  importJobUrl,
  previewManualJobAnalysis,
  previewJobAnalysis,
  saveAnalyzedJob,
} from "../../services/jobApi";
import type { JobImportDraft, MatchReport } from "../../types/job";
import type { NavigationJob } from "../../types/dashboard";
import { PageFeedback } from "../../components/PageFeedback";
import { useT } from "../../i18n/LanguageProvider";

const JOB_ANALYSIS_SESSION_KEY = "applyease.job-analysis-draft.v1";

type JobAnalysisSession = {
  title: string;
  company: string;
  description: string;
  jobCategory: string;
  location: string;
  requiredSkillsInput: string;
  responsibilitiesInput: string;
  importedDraft: JobImportDraft | null;
  report: MatchReport | null;
  importNeedsManualDescription: boolean;
};

function readJobAnalysisSession(): JobAnalysisSession | null {
  try {
    const raw = window.sessionStorage.getItem(JOB_ANALYSIS_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<JobAnalysisSession>;
    if (typeof parsed.title !== "string" || typeof parsed.description !== "string") return null;
    return {
      title: parsed.title,
      company: typeof parsed.company === "string" ? parsed.company : "",
      description: parsed.description,
      jobCategory: typeof parsed.jobCategory === "string" ? parsed.jobCategory : "",
      location: typeof parsed.location === "string" ? parsed.location : "",
      requiredSkillsInput:
        typeof parsed.requiredSkillsInput === "string" ? parsed.requiredSkillsInput : "",
      responsibilitiesInput:
        typeof parsed.responsibilitiesInput === "string" ? parsed.responsibilitiesInput : "",
      importedDraft: parsed.importedDraft ?? null,
      report: parsed.report ?? null,
      importNeedsManualDescription: Boolean(parsed.importNeedsManualDescription),
    };
  } catch {
    return null;
  }
}

export function JobAnalysisPage({
  onJobAnalyzed,
  onReturnToDashboard,
  onOpenResourcePlan,
  initialJob,
  hideHero = false,
}: {
  onJobAnalyzed?: (job: NavigationJob) => void;
  onReturnToDashboard?: () => void;
  onOpenResourcePlan?: (job: NavigationJob) => void;
  initialJob?: NavigationJob;
  hideHero?: boolean;
}) {
  const [restoredSession] = useState<JobAnalysisSession | null>(() => readJobAnalysisSession());
  const [title, setTitle] = useState(() => restoredSession?.title ?? "");
  const [company, setCompany] = useState(() => restoredSession?.company ?? "");
  const [description, setDescription] = useState(() => restoredSession?.description ?? "");
  const [jobCategory, setJobCategory] = useState(() => restoredSession?.jobCategory ?? "");
  const [location, setLocation] = useState(() => restoredSession?.location ?? "");
  const [requiredSkillsInput, setRequiredSkillsInput] = useState(
    () => restoredSession?.requiredSkillsInput ?? "",
  );
  const [responsibilitiesInput, setResponsibilitiesInput] = useState(
    () => restoredSession?.responsibilitiesInput ?? "",
  );
  const [url, setUrl] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(false);
  const [importedDraft, setImportedDraft] = useState<JobImportDraft | null>(
    () => restoredSession?.importedDraft ?? null,
  );

  const [report, setReport] = useState<MatchReport | null>(() => restoredSession?.report ?? null);
  const [activeAction, setActiveAction] = useState<
    "loading-report" | "import-url" | "import-screenshot" | "analyze" | "save" | null
  >(null);
  const [error, setError] = useState("");
  const [importNeedsManualDescription, setImportNeedsManualDescription] = useState(
    () => restoredSession?.importNeedsManualDescription ?? false,
  );
  const [decisionDismissed, setDecisionDismissed] = useState(false);
  const [confirmedEligibility, setConfirmedEligibility] = useState<Set<string>>(new Set());

  const t = useT();

  // Keep unsaved analysis work available while the student moves between
  // workspaces. sessionStorage is deliberately used instead of the database:
  // a preview stays private to this browser session until the student chooses
  // to add it to the job workspace.
  useEffect(() => {
    const draft: JobAnalysisSession = {
      title,
      company,
      description,
      jobCategory,
      location,
      requiredSkillsInput,
      responsibilitiesInput,
      importedDraft,
      report,
      importNeedsManualDescription,
    };
    try {
      window.sessionStorage.setItem(JOB_ANALYSIS_SESSION_KEY, JSON.stringify(draft));
    } catch {
      // Private browsing or a full storage quota must not block analysis.
    }
  }, [
    title,
    company,
    description,
    jobCategory,
    location,
    requiredSkillsInput,
    responsibilitiesInput,
    importedDraft,
    report,
    importNeedsManualDescription,
  ]);

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
        setConfirmedEligibility(new Set());
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

  const applyDraft = (draft: JobImportDraft) => {
    setImportedDraft(draft);
    setImportNeedsManualDescription(draft.needs_manual_description);
  };

  const showPreview = async (payload: { title: string; company: string; description: string }) => {
    const preview = await previewJobAnalysis(payload);
    setReport(preview);
    setDecisionDismissed(false);
    setConfirmedEligibility(new Set());
  };

  const analyzeImportedDraft = async (draft: JobImportDraft) => {
    if (draft.description.trim().length < 20) {
      setImportNeedsManualDescription(true);
      return;
    }
    setActiveAction("analyze");
    try {
      await showPreview({
        title: draft.title || "Untitled role",
        company: draft.company,
        description: draft.description,
      });
    } finally {
      setActiveAction(null);
    }
  };

  const importUrl = async () => {
    setActiveAction("import-url");
    setError("");
    setImportNeedsManualDescription(false);
    setReport(null);
    setImportedDraft(null);
    try {
      const draft = await importJobUrl(url);
      applyDraft(draft);
      await analyzeImportedDraft(draft);
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
    setReport(null);
    setImportedDraft(null);
    try {
      const draft = await importJobScreenshot(file, consent);
      applyDraft(draft);
      await analyzeImportedDraft(draft);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("job.recognizing"));
    } finally {
      setActiveAction(null);
    }
  };

  const manualRoleDescription = [
    description.trim(),
    jobCategory.trim() && `Job category: ${jobCategory.trim()}`,
    location.trim() && `Location: ${location.trim()}`,
    requiredSkillsInput.trim() && `Required skills: ${requiredSkillsInput.trim()}`,
    responsibilitiesInput.trim() && `Key responsibilities: ${responsibilitiesInput.trim()}`,
  ].filter(Boolean).join("\n");

  const splitManualItems = (value: string) =>
    value.split(/[,\n，]/).map((item) => item.trim()).filter(Boolean);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setActiveAction("analyze");
    try {
      const preview = await previewManualJobAnalysis({
        title: title || "Untitled role",
        company,
        job_category: jobCategory,
        location,
        required_skills: splitManualItems(requiredSkillsInput),
        responsibilities: splitManualItems(responsibilitiesInput),
        additional_details: description,
      });
      setReport(preview);
      setDecisionDismissed(false);
      setConfirmedEligibility(new Set());
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
      {!hideHero && <header className="product-hero">
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
      </header>}
      <section className="product-content job-workspace">
        <div className="job-input-stack">
          <div className="card import-panel">
            <p className="section-kicker">01 · IMPORT</p>
            <h2>{t("job.importTitle")}</h2>
            <p className="privacy-note">{t("job.importAutoAnalyse")}</p>
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
          {importedDraft ? (
            <section className="card imported-analysis-card" aria-live="polite">
              <p className="section-kicker">02 · IMPORTED ROLE ANALYSIS</p>
              <div className="imported-analysis-heading">
                <div>
                  <h2>{importedDraft.title}</h2>
                  {importedDraft.company && <p>{importedDraft.company}</p>}
                </div>
                <span className={activeAction === "analyze" ? "is-analyzing" : ""}>
                  {activeAction === "analyze"
                    ? t("job.analyzing")
                    : report
                      ? t("job.importedReady")
                      : t("job.importedNeedsDetails")}
                </span>
              </div>
              {importedDraft.location && (
                <p className="imported-analysis-meta">{t("job.location", { loc: importedDraft.location })}</p>
              )}
              {importedDraft.source_url && (
                <p className="imported-analysis-meta">{t("job.source", { url: importedDraft.source_url })}</p>
              )}
              <p className="privacy-note">
                {activeAction === "analyze"
                  ? t("job.importedAnalysing")
                  : report
                    ? t("job.importedAnalysisDone")
                    : t("job.importNeedsManualDescription")}
              </p>
              {report && (
                <a className="imported-analysis-result-link" href="#job-analysis-result">
                  {t("job.viewImportedAnalysis")}
                  <span aria-hidden="true">↓</span>
                </a>
              )}
              <button
                type="button"
                className="secondary"
                disabled={activeAction !== null}
                onClick={() => {
                  setImportedDraft(null);
                  setReport(null);
                  setImportNeedsManualDescription(false);
                }}
              >
                {t("job.switchToManual")}
              </button>
            </section>
          ) : (
          <form className="card analysis-form" onSubmit={submit}>
            <p className="section-kicker">02 · MANUAL ROLE BRIEF</p>
            <h2>{t("job.manualTitle")}</h2>
            <p className="privacy-note">{t("job.manualSub")}</p>
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
              {t("job.manualCategory")}
              <input
                value={jobCategory}
                onChange={(e) => setJobCategory(e.target.value)}
                placeholder={t("job.manualCategoryPlaceholder")}
              />
            </label>
            <label>
              {t("job.manualLocation")}
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Hong Kong / Remote"
              />
            </label>
            <label>
              {t("job.manualSkills")}
              <input
                value={requiredSkillsInput}
                onChange={(e) => setRequiredSkillsInput(e.target.value)}
                placeholder="Python, SQL, communication"
              />
            </label>
            <label className="manual-role-wide">
              {t("job.manualResponsibilities")}
              <textarea
                value={responsibilitiesInput}
                onChange={(e) => setResponsibilitiesInput(e.target.value)}
                placeholder={t("job.manualResponsibilitiesPlaceholder")}
              />
            </label>
            <label className="manual-role-wide">
              {t("job.manualDetails")}
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("job.manualDetailsPlaceholder")}
              />
            </label>
            <button
              disabled={
                activeAction !== null ||
                manualRoleDescription.length < 20
              }
            >
              {activeAction === "analyze" ? t("job.analyzing") : t("job.analyzeManual")}
            </button>
          </form>
          )}
        </div>
        {error && <PageFeedback kind="error" message={error} />}
        {importNeedsManualDescription && (
          <PageFeedback kind="info" message={t("job.importNeedsManualDescription")} />
        )}
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
              confirmedEligibility={confirmedEligibility}
              onConfirmEligibility={(requirement) =>
                setConfirmedEligibility((current) => new Set(current).add(requirement))
              }
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
  confirmedEligibility,
  onConfirmEligibility,
}: {
  report: MatchReport;
  canGeneratePlan: boolean;
  onOpenResourcePlan?: (job: NavigationJob) => void;
  confirmedEligibility: Set<string>;
  onConfirmEligibility: (requirement: string) => void;
}) {
  const t = useT();

  const requiredMissing =
    report.missing_required_skills ?? report.missing_skills;

  const preferredMissing = report.missing_preferred_skills ?? [];

  const matchedRequired =
    report.matched_required_skills ?? report.matched_skills;

  const matchedPreferred = report.matched_preferred_skills ?? [];

  const eligibilityChecks = report.eligibility_checks ?? [];
  // A single sentence in a posting can be classified under more than one
  // eligibility type (for example, graduation timing and student status).
  // Show it once, while retaining all applicable labels, so the student is
  // not asked to review the same requirement twice.
  const groupedEligibilityChecks = eligibilityChecks.reduce<
    Array<{ check: (typeof eligibilityChecks)[number]; kinds: string[] }>
  >((groups, check) => {
    const existing = groups.find(
      (group) =>
        group.check.requirement === check.requirement &&
        group.check.evidence === check.evidence &&
        group.check.status === check.status,
    );
    if (existing) {
      if (!existing.kinds.includes(check.kind)) existing.kinds.push(check.kind);
    } else {
      groups.push({ check, kinds: [check.kind] });
    }
    return groups;
  }, []);
  const unresolvedEligibility = eligibilityChecks.filter(
    (check) => check.status === "needs_confirmation" && !confirmedEligibility.has(check.requirement),
  );
  const eligibilityVerdict = unresolvedEligibility.length
    ? "confirm"
    : requiredMissing.length
      ? "prepare"
      : "ready";

  const labels: Record<string, string> = {
    required_skill_match: t("ai.feature.job_match"),
    preferred_skill_match: t("job.preferredSkills"),
    experience_relevance: t("job.hero.title"),
    quantified_evidence: t("shared.sources"),
    education_background: t("builder.exportTitle"),
    qualification_coverage: t("job.qualifications"),
  };

  return (
    <div className="report" id="job-analysis-result" tabIndex={-1}>
      {eligibilityChecks.length > 0 && (
        <section className={`card eligibility-gate eligibility-${eligibilityVerdict}`}>
          <p className="section-kicker">APPLYEASE · ELIGIBILITY CHECK</p>
          <h2>{t(`job.eligibilityVerdict.${eligibilityVerdict}`)}</h2>
          <p>{t(`job.eligibilityVerdictDetail.${eligibilityVerdict}`)}</p>
          <ul>
            {groupedEligibilityChecks.map(({ check, kinds }) => {
              const isMet = check.status === "met" || confirmedEligibility.has(check.requirement);
              return (
                <li key={`${check.kind}-${check.requirement}`}>
                  <div>
                    <strong>
                      {kinds.map((kind) => t(`job.eligibilityKind.${kind}`)).join(" · ")}
                    </strong>
                    <span>{check.requirement}</span>
                    {check.evidence && <small>{check.evidence}</small>}
                  </div>
                  {isMet ? (
                    <span className="eligibility-status met">{t("job.eligibilityMet")}</span>
                  ) : (
                    <button
                      type="button"
                      className="secondary eligibility-confirm"
                      onClick={() => onConfirmEligibility(check.requirement)}
                    >
                      {t("job.eligibilityConfirm")}
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
          <small className="privacy-note">{t("job.eligibilitySafetyNote")}</small>
        </section>
      )}
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
    </div>
  );
}
