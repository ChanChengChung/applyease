import { useEffect, useMemo, useRef, useState } from "react";
import { MaterialEditor } from "../../components/MaterialEditor";
import { EvidenceTracing } from "../../components/EvidenceTracing";
import { ApplicationIntegrityGate } from "../../components/ApplicationIntegrityGate";
import { PageFeedback } from "../../components/PageFeedback";
import {
  ResumePreview,
  splitResumeSections,
} from "../../components/ResumePreview";
import {
  deleteApplicantProfile,
  getApplicantProfile,
  saveApplicantProfile,
} from "../../services/applicantProfileApi";
import {
  downloadResume,
  generateAnswer,
  generateCoverLetter,
  generateResume,
  listMaterials,
  saveDownload,
  updateMaterial,
} from "../../services/materialApi";
import {
  analyzeJob,
  getApplicationReadiness,
  importJobUrl,
  listJobs,
} from "../../services/jobApi";
import type { Job } from "../../types/job";
import type { ApplicationReadiness } from "../../types/job";
import type {
  Material,
  OutputLanguage,
  ResumeAccent,
  AnswerTone,
  ResumeAppearance,
  ResumeDensity,
  ResumeFontStyle,
  ResumeTemplate,
} from "../../types/material";
import { useI18n, useT } from "../../i18n/LanguageProvider";

export function ApplicationBuilderPage({
  initialJobId,
  onJobSelected,
  onReturnToDashboard,
  onOpenApplicationForm,
}: {
  initialJobId?: number;
  onJobSelected?: (job: { id: number; title: string; company: string }) => void;
  onReturnToDashboard?: () => void;
  onOpenApplicationForm?: (jobId: number) => void;
}) {
  const [jobId, setJobId] = useState(initialJobId ? String(initialJobId) : "");
  const [question, setQuestion] = useState("");
  const [limit, setLimit] = useState("300");
  const [answerTone, setAnswerTone] = useState<AnswerTone>("professional");
  const [desiredContent, setDesiredContent] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [targetCreatorOpen, setTargetCreatorOpen] = useState(false);
  const [targetCreatorMode, setTargetCreatorMode] = useState<"link" | "manual">("link");
  const [targetUrl, setTargetUrl] = useState("");
  const [newTargetTitle, setNewTargetTitle] = useState("");
  const [newTargetCompany, setNewTargetCompany] = useState("");
  const [newTargetDescription, setNewTargetDescription] = useState("");

  const [material, setMaterial] = useState<Material | null>(null);
  const [history, setHistory] = useState<Material[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const [template, setTemplate] = useState<ResumeTemplate>("modern");
  const [fontStyle, setFontStyle] = useState<ResumeFontStyle>("default");
  const [density, setDensity] = useState<ResumeDensity>("standard");
  const [accent, setAccent] = useState<ResumeAccent>("template");
  const [includeSources, setIncludeSources] = useState(false);
  const [exporting, setExporting] = useState<"docx" | "pdf" | "">("");

  const [displayName, setDisplayName] = useState("");
  const [contactLine, setContactLine] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [hiddenSections, setHiddenSections] = useState<string[]>([]);
  const [readiness, setReadiness] = useState<ApplicationReadiness | null>(null);
  const { language } = useI18n();
  const [outputLanguage, setOutputLanguage] = useState<OutputLanguage>(language);
  const questionInput = useRef<HTMLTextAreaElement>(null);
  const [comparison, setComparison] = useState<Material | null>(null);
  // `null` means the editor has not yet supplied a draft. An empty string is
  // still a valid user edit and must therefore be reflected in the preview.
  const [liveResumeText, setLiveResumeText] = useState<string | null>(null);

  // Deterministic pipeline steps shown while generating. These mirror the
  // backend order (retrieve confirmed experience → match role evidence →
  // generate grounded material) so the AI process is visible during the wait.
  const GENERATION_STEPS = ["retrieving", "matching", "generating"] as const;
  const [stepIndex, setStepIndex] = useState(-1);

  const t = useT();

  useEffect(() => {
    setOutputLanguage(language);
  }, [language]);

  const readinessVars = (params?: Record<string, unknown>) => {
    const vars: Record<string, string | number> = {};
    Object.entries(params || {}).forEach(([key, value]) => {
      if (Array.isArray(value)) vars[key] = value.join(" · ");
      else if (typeof value === "string" || typeof value === "number") vars[key] = value;
    });
    return vars;
  };

  const readinessDetail = (item: {
    code: string;
    severity: string;
    detail: string;
    params?: Record<string, unknown>;
  }) => {
    let state: string = item.severity;
    if (item.code === "resume" && item.severity === "blocker") {
      state = item.params?.has_draft ? "fix" : "generate";
    }
    return t(`readiness.${item.code}.${state}`, readinessVars(item.params));
  };

  const readinessTitle = (item: { code: string }) =>
    t(`readiness.${item.code}.title`);

  const displayedMaterial = material || history[0] || null;
  const materialHistory = history.length > 0 && (
    <div className="card material-history-card">
      <div className="material-history-heading">
        <div>
          <p className="section-kicker">{t("builder.historyKicker")}</p>
          <h2>{t("builder.historyTitle")}</h2>
          <p className="privacy-note">{t("builder.historySub")}</p>
        </div>
        <span className="history-count">{t("builder.historyCount", { n: history.length })}</span>
      </div>
      <ul className="history-version-list">
        {history.map((version) => (
          <li key={version.id} className={displayedMaterial?.id === version.id ? "active" : ""}>
            <button type="button" onClick={() => { setMaterial(version); setComparison(null); }}>
              #{version.id} · {version.material_type} ·{" "}
              {version.generation_method || t("builder.ruleMethod")}
            </button>{" "}
            <small>{new Date(version.created_at).toLocaleString()}</small>
            <button
              type="button"
              className="history-compare"
              onClick={() => setComparison(version)}
            >
              {t("builder.compareVersion")}
            </button>
          </li>
        ))}
      </ul>
      {comparison && displayedMaterial && comparison.id !== displayedMaterial.id && (
        <div className="version-comparison">
          <div>
            <strong>{t("builder.currentVersion")}</strong>
            <pre>{displayedMaterial.text}</pre>
          </div>
          <div>
            <strong>{t("builder.selectedVersion")}</strong>
            <pre>{comparison.text}</pre>
          </div>
        </div>
      )}
    </div>
  );

  useEffect(() => {
    void getApplicantProfile()
      .then((profile) => {
        if (profile) {
          setDisplayName(profile.display_name);
          setContactLine(profile.contact_line);
          setEmail(profile.email || "");
          setPhone(profile.phone || "");
          setLocation(profile.location || "");
          setLinkedinUrl(profile.linkedin_url || "");
          setGithubUrl(profile.github_url || "");
        }
      })
      .catch(() => undefined);
  }, []);
  useEffect(() => {
    if (initialJobId) setJobId(String(initialJobId));
  }, [initialJobId]);
  useEffect(() => {
    setLiveResumeText(
      material?.material_type === "resume" ? material.text : "",
    );
  }, [material?.id, material?.material_type, material?.text]);
  useEffect(() => {
    void listJobs()
      .then(setJobs)
      .catch(() => setJobs([]));
  }, []);
  useEffect(() => {
    const id = Number(jobId);
    if (!Number.isInteger(id) || id <= 0) {
      setReadiness(null);
      return;
    }
    // The action deck should describe this role's current state without
    // requiring the applicant to discover a separate preflight button first.
    void getApplicationReadiness(id)
      .then(setReadiness)
      .catch(() => setReadiness(null));
  }, [jobId]);

  const validJobId = () => {
    const id = Number(jobId);
    if (!Number.isInteger(id) || id <= 0) {
      setError(t("builder.invalidJobId"));
      return null;
    }
    return id;
  };

  const refreshHistory = async (id: number) => {
    const versions = await listMaterials(id);
    setHistory(versions);
    return versions;
  };

  const selectTargetJob = (job: Job) => {
    setJobs((current) => [job, ...current.filter((item) => item.id !== job.id)]);
    setJobId(String(job.id));
    onJobSelected?.({ id: job.id, title: job.title, company: job.company });
  };

  const createTargetFromLink = async () => {
    if (!targetUrl.trim()) return;
    setBusy(true);
    setError("");
    try {
      // URL import extracts the public job page first; analyse then persists a
      // structured target role so matching, RAG and material generation all
      // use the same job record.
      const draft = await importJobUrl(targetUrl.trim());
      const job = await analyzeJob({
        title: draft.title || "Untitled role",
        company: draft.company,
        description: draft.description,
      });
      selectTargetJob(job);
      setTargetCreatorOpen(false);
      setTargetUrl("");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.targetCreateFailed"));
    } finally {
      setBusy(false);
    }
  };

  const createTargetManually = async () => {
    if (newTargetDescription.trim().length < 20) {
      setError(t("builder.targetDescriptionRequired"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const job = await analyzeJob({
        title: newTargetTitle.trim() || "Untitled role",
        company: newTargetCompany.trim(),
        description: newTargetDescription.trim(),
      });
      selectTargetJob(job);
      setTargetCreatorOpen(false);
      setNewTargetTitle("");
      setNewTargetCompany("");
      setNewTargetDescription("");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.targetCreateFailed"));
    } finally {
      setBusy(false);
    }
  };

  const run = async (kind: "resume" | "cover" | "answer") => {
    const id = validJobId();
    if (!id) return;
    setBusy(true);
    setError("");
    setStepIndex(0);
    // Advance the visible pipeline step on a cadence so the wait shows progress.
    const stepTimer = setInterval(
      () =>
        setStepIndex((current) =>
          Math.min(current + 1, GENERATION_STEPS.length - 1),
        ),
      700,
    );
    try {
      const generated =
        kind === "resume"
          ? await generateResume(id, outputLanguage)
          : kind === "cover"
            ? await generateCoverLetter(id, outputLanguage)
            : await generateAnswer(id, question, Number(limit), outputLanguage, {
                tone: answerTone,
                desiredContent: desiredContent.trim(),
              });
      setMaterial(generated);
      await refreshHistory(id);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.genFailed"));
    } finally {
      clearInterval(stepTimer);
      setStepIndex(-1);
      setBusy(false);
    }
  };

  const loadHistory = async () => {
    const id = validJobId();
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      const versions = await refreshHistory(id);
      if (versions[0]) {
        setMaterial(versions[0]);
        setComparison(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.historyFailed"));
    } finally {
      setBusy(false);
    }
  };
  const checkReadiness = async () => {
    const id = validJobId();
    if (!id) return;
    setBusy(true);
    setError("");
    try {
      setReadiness(await getApplicationReadiness(id));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.genFailed"));
    } finally {
      setBusy(false);
    }
  };

  const recommendation = useMemo(() => {
    if (!jobId) return t("builder.recommendChooseRole");
    if (!readiness) return t("builder.recommendCheckProgress");
    if (readiness.primary_action) return readinessDetail(readiness.primary_action);
    if (readiness.ready_to_submit) return t("builder.recommendReview");
    return t("builder.recommendCheckProgress");
  }, [jobId, readiness, t]);

  const selectedJob = useMemo(
    () => jobs.find((job) => String(job.id) === jobId),
    [jobId, jobs],
  );

  const save = async (text: string) => {
    if (!material) return;
    const updated = await updateMaterial(material.id, text);
    setMaterial(updated);
    await refreshHistory(updated.job_id);
  };

  const sections = useMemo(
    () =>
      material?.material_type === "resume"
        ? splitResumeSections(material.text).map((item) => item.name)
        : [],
    [material],
  );

  useEffect(() => {
    setSectionOrder((current) => [
      ...current.filter((name) => sections.includes(name)),
      ...sections.filter((name) => !current.includes(name)),
    ]);
    setHiddenSections((current) =>
      current.filter((name) => sections.includes(name)),
    );
  }, [sections.join("|")]);

  const moveSection = (name: string, direction: -1 | 1) =>
    setSectionOrder((current) => {
      const index = current.indexOf(name);
      const target = index + direction;
      if (index < 0 || target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });

  const exportCurrent = async (format: "docx" | "pdf") => {
    if (!material || material.material_type !== "resume" || !displayName.trim())
      return;
    setExporting(format);
    setError("");
    try {
      saveDownload(
        await downloadResume(
          material.id,
          format,
          template,
          includeSources,
          displayName.trim(),
          contactLine.trim(),
          {
            email: email.trim(),
            phone: phone.trim(),
            location: location.trim(),
            linkedin_url: linkedinUrl.trim(),
            github_url: githubUrl.trim(),
          },
          sectionOrder,
          hiddenSections,
          { fontStyle, density, accent },
        ),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("builder.exporting"));
    } finally {
      setExporting("");
    }
  };

  const persistProfile = async () => {
    if (!displayName.trim()) {
      setProfileMessage(t("builder.nameRequired"));
      return;
    }
    setProfileBusy(true);
    try {
      await saveApplicantProfile(displayName.trim(), contactLine.trim(), {
        email: email.trim(),
        phone: phone.trim(),
        location: location.trim(),
        linkedin_url: linkedinUrl.trim(),
        github_url: githubUrl.trim(),
      });
      setProfileMessage(t("builder.profileSaved"));
    } catch (e) {
      setProfileMessage(
        e instanceof Error ? e.message : t("builder.profileSaveFailed"),
      );
    } finally {
      setProfileBusy(false);
    }
  };

  const removeProfile = async () => {
    setProfileBusy(true);
    try {
      await deleteApplicantProfile();
      setDisplayName("");
      setContactLine("");
      setEmail("");
      setPhone("");
      setLocation("");
      setLinkedinUrl("");
      setGithubUrl("");
      setProfileMessage(t("builder.profileDeleted"));
    } catch (e) {
      setProfileMessage(
        e instanceof Error ? e.message : t("builder.profileDeleteFailed"),
      );
    } finally {
      setProfileBusy(false);
    }
  };

  const materialTypes = new Set(history.map((item) => item.material_type));
  const complete =
    materialTypes.has("resume") && materialTypes.has("cover_letter");
  const exportDisabled =
    Boolean(exporting) ||
    !material?.fact_check_passed ||
    !displayName.trim() ||
    sections.length === hiddenSections.length;
  const resumeAppearance: ResumeAppearance = { fontStyle, density, accent };
  // Keep visual controls beside the live paper rather than below the editor.
  // Each change is previewed immediately and is also passed to DOCX/PDF export.
  const resumeAppearanceControls = (
    <section className="resume-design-controls" aria-label={t("builder.designControls")}>
      <p className="section-kicker">{t("builder.designControls")}</p>
      <div className="resume-appearance-grid">
        <label>
          {t("builder.template")}
          <select
            aria-label={t("builder.template")}
            value={template}
            onChange={(e) => setTemplate(e.target.value as ResumeTemplate)}
          >
            <option value="classic">{t("builder.tpl.classic")}</option>
            <option value="modern">{t("builder.tpl.modern")}</option>
            <option value="compact">{t("builder.tpl.compact")}</option>
          </select>
        </label>
        <label>
          {t("builder.fontStyle")}
          <select
            aria-label={t("builder.fontStyle")}
            value={fontStyle}
            onChange={(e) => setFontStyle(e.target.value as ResumeFontStyle)}
          >
            <option value="default">{t("builder.font.default")}</option>
            <option value="serif">{t("builder.font.serif")}</option>
            <option value="microsoft_yahei">{t("builder.font.yahei")}</option>
            <option value="sans">{t("builder.font.sans")}</option>
          </select>
        </label>
        <label>
          {t("builder.density")}
          <select
            aria-label={t("builder.density")}
            value={density}
            onChange={(e) => setDensity(e.target.value as ResumeDensity)}
          >
            <option value="relaxed">{t("builder.density.relaxed")}</option>
            <option value="standard">{t("builder.density.standard")}</option>
            <option value="compact">{t("builder.density.compact")}</option>
          </select>
        </label>
        <label>
          {t("builder.accent")}
          <select
            aria-label={t("builder.accent")}
            value={accent}
            onChange={(e) => setAccent(e.target.value as ResumeAccent)}
          >
            <option value="template">{t("builder.accent.template")}</option>
            <option value="navy">{t("builder.accent.navy")}</option>
            <option value="black">{t("builder.accent.black")}</option>
          </select>
        </label>
      </div>
    </section>
  );

  return (
    <main className="product-page builder-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· APPLICATION BUILDER</span>
          </p>
          <h1>{t("builder.hero.title")}</h1>
          <p className="sub">{t("builder.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-builder" aria-hidden="true">
          <span>▣</span>
        </div>
      </header>
      <section className="product-content">
        {complete && (
          <PageFeedback
            kind="success"
            message={t("builder.ready")}
            actionLabel={t("profile.backToDashboard")}
            onAction={onReturnToDashboard}
          />
        )}
        <div className="card builder-control-panel" aria-busy={busy}>
          <div className="builder-studio-heading">
            <p className="section-kicker">01 · MATERIAL STUDIO</p>
            <div>
              <h2>{t("builder.actionTitle")}</h2>
              <p>{t("builder.actionSub")}</p>
            </div>
          </div>
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
          <button
            type="button"
            className="target-creator-toggle"
            onClick={() => setTargetCreatorOpen((open) => !open)}
          >
            {targetCreatorOpen ? t("builder.closeTargetCreator") : t("builder.addTarget")}
          </button>
          {targetCreatorOpen && (
            <section className="target-creator" aria-label={t("builder.addTarget")}>
              <div className="target-creator-tabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={targetCreatorMode === "link"}
                  className={targetCreatorMode === "link" ? "active" : ""}
                  onClick={() => setTargetCreatorMode("link")}
                >
                  {t("builder.targetFromLink")}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={targetCreatorMode === "manual"}
                  className={targetCreatorMode === "manual" ? "active" : ""}
                  onClick={() => setTargetCreatorMode("manual")}
                >
                  {t("builder.targetManual")}
                </button>
              </div>
              {targetCreatorMode === "link" ? (
                <div className="target-link-row">
                  <label>
                    {t("builder.targetUrl")}
                    <input
                      type="url"
                      value={targetUrl}
                      onChange={(event) => setTargetUrl(event.target.value)}
                      placeholder="https://jobs.lever.co/..."
                    />
                  </label>
                  <button type="button" disabled={busy || !targetUrl.trim()} onClick={() => void createTargetFromLink()}>
                    {t("builder.importAndAnalyze")}
                  </button>
                </div>
              ) : (
                <div className="target-manual-grid">
                  <label>{t("job.field.title")}<input value={newTargetTitle} onChange={(event) => setNewTargetTitle(event.target.value)} /></label>
                  <label>{t("job.field.company")}<input value={newTargetCompany} onChange={(event) => setNewTargetCompany(event.target.value)} /></label>
                  <label className="target-description">{t("job.field.description")}<textarea value={newTargetDescription} onChange={(event) => setNewTargetDescription(event.target.value)} /></label>
                  <button type="button" disabled={busy || newTargetDescription.trim().length < 20} onClick={() => void createTargetManually()}>{t("builder.analyzeAndUseTarget")}</button>
                </div>
              )}
              <p>{t("builder.targetCreatorNote")}</p>
            </section>
          )}
          <label>
            {t("builder.outputLanguage")}
            <select
              aria-label={t("builder.outputLanguage")}
              value={outputLanguage}
              onChange={(event) =>
                setOutputLanguage(event.target.value as OutputLanguage)
              }
            >
              <option value="en">{t("builder.language.en")}</option>
              <option value="zh-CN">{t("builder.language.zhCN")}</option>
              <option value="zh-TW">{t("builder.language.zhTW")}</option>
            </select>
          </label>
          {!jobs.length && (
            <p className="privacy-note">{t("resource.noTargets")}</p>
          )}
          {busy && stepIndex >= 0 && (
            <ol className="generation-steps" aria-label={t("gen.stepsTitle")}>
              {GENERATION_STEPS.map((step, index) => (
                <li
                  key={step}
                  className={
                    index < stepIndex
                      ? "done"
                      : index === stepIndex
                        ? "active"
                        : "pending"
                  }
                >
                  <span className="step-dot" aria-hidden="true">
                    {index < stepIndex ? "✓" : index === stepIndex ? "◌" : "·"}
                  </span>
                  {t(`gen.step.${step}`)}
                </li>
              ))}
            </ol>
          )}
          <div className="builder-action-deck">
            <div className="builder-action-intro">
              <span aria-hidden="true">✦</span>
              <div>
                <strong>{t("builder.actionPrimary")}</strong>
                <small>{recommendation}</small>
              </div>
            </div>
            <div className="builder-primary-actions">
              <button
                className="builder-resume-cta"
                aria-label={t("builder.genResume")}
                disabled={busy || !jobId}
                onClick={() => void run("resume")}
              >
                <span className="builder-action-icon" aria-hidden="true">
                  ▤
                </span>
                <span>
                  <strong>{t("builder.genResume")}</strong>
                  <small>{t("builder.resumeCtaHelp")}</small>
                </span>
              </button>
              <button
                className="builder-cover-cta"
                aria-label={t("builder.genCover")}
                disabled={busy || !jobId}
                onClick={() => void run("cover")}
              >
                <span className="builder-action-icon" aria-hidden="true">
                  ✉
                </span>
                <span>
                  <strong>{t("builder.genCover")}</strong>
                  <small>{t("builder.coverCtaHelp")}</small>
                </span>
              </button>
            </div>
            <div className="builder-secondary-actions">
              <button
                disabled={busy || !jobId}
                onClick={() => void loadHistory()}
              >
                {t("builder.loadHistory")}
              </button>
              <button
                disabled={busy || !jobId}
                onClick={() => void checkReadiness()}
              >
                {t("builder.preflight")}
              </button>
            </div>
          </div>
          <section className="application-question-studio">
            <div className="question-studio-heading">
              <span aria-hidden="true">✦</span>
              <div>
                <p className="section-kicker">02 · APPLICATION ANSWERS</p>
                <h3>{t("builder.questionGuideTitle")}</h3>
                <p>{t("builder.questionGuideSub")}</p>
              </div>
              <div className="question-studio-actions">
                <button
                  type="button"
                  className="ghost-action"
                  onClick={() => {
                    setQuestion("");
                    questionInput.current?.focus();
                  }}
                >
                  {t("builder.addQuestion")}
                </button>
                <button
                  type="button"
                  className="link-import-action"
                  disabled={!jobId}
                  onClick={() => onOpenApplicationForm?.(Number(jobId))}
                >
                  {t("builder.importQuestionLink")}
                </button>
              </div>
            </div>
            <div className="question-input-grid">
              <label>
                {t("builder.question")}
                <textarea
                  ref={questionInput}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={t("builder.questionPlaceholder")}
                />
              </label>
              <label>
                {t("builder.maxChars")}
                <input
                  type="number"
                  min="50"
                  max="5000"
                  value={limit}
                  onChange={(e) => setLimit(e.target.value)}
                />
              </label>
              <label>
                {t("builder.answerTone")}
                <select
                  value={answerTone}
                  onChange={(event) =>
                    setAnswerTone(event.target.value as AnswerTone)
                  }
                >
                  <option value="professional">{t("builder.tone.professional")}</option>
                  <option value="concise">{t("builder.tone.concise")}</option>
                  <option value="enthusiastic">{t("builder.tone.enthusiastic")}</option>
                  <option value="technical">{t("builder.tone.technical")}</option>
                  <option value="reflective">{t("builder.tone.reflective")}</option>
                </select>
              </label>
              <label className="question-preference-field">
                {t("builder.desiredContent")}
                <input
                  aria-label={t("builder.desiredContent")}
                  value={desiredContent}
                  maxLength={1000}
                  onChange={(event) => setDesiredContent(event.target.value)}
                  placeholder={t("builder.desiredContentPlaceholder")}
                />
                <small>{t("builder.desiredContentHelp")}</small>
              </label>
              <button
                className="question-generate-cta"
                disabled={
                  busy ||
                  !jobId ||
                  question.trim().length < 5 ||
                  Number(limit) < 50 ||
                  Number(limit) > 5000
                }
                onClick={() => void run("answer")}
              >
                {busy ? t("builder.processing") : t("builder.genAnswer")}
              </button>
            </div>
          </section>
        </div>

        {error && <PageFeedback kind="error" message={error} />}
        {(materialHistory || readiness) && (
          <section className="material-follow-up" aria-live="polite">
            {materialHistory}
            {readiness && (
              <section className="card preflight-review-card">
                <div className="preflight-review-heading">
                  <div>
                    <p className="section-kicker">{t("builder.preflightKicker")}</p>
                    <h2>
                      {t("builder.readinessFor", {
                        role: selectedJob?.title || t("builder.selectedRoleFallback"),
                        company: selectedJob?.company || t("builder.unknownCompany"),
                      })}
                    </h2>
                    <p className="decision-verdict">
                      {readiness.ready_to_submit
                        ? t("builder.readinessRecommended")
                        : t("builder.readinessNeedsPreparation")}
                    </p>
                  </div>
                  <div className="preflight-score" aria-label={t("builder.matchScore", { score: readiness.match_score, warnings: readiness.warnings })}>
                    <strong>{readiness.match_score}</strong><small>/100</small>
                    <span>{t("builder.preflightScore")}</span>
                  </div>
                </div>
                <div className="preflight-items">
                  {readiness.items.map((item) => (
                    <article key={item.code} className={`preflight-item ${item.severity}`}>
                      <span aria-hidden="true">{item.severity === "pass" ? "✓" : "!"}</span>
                      <div>
                        <strong>{readinessTitle(item)}</strong>
                        <p>{readinessDetail(item)}</p>
                      </div>
                    </article>
                  ))}
                </div>
                <small className="privacy-note">{t("builder.readinessDisclaimer")}</small>
              </section>
            )}
          </section>
        )}

        {material?.material_type === "resume" && (
          <section
            className="resume-workbench"
            aria-label={t("builder.exportTitle")}
          >
            <aside className="resume-workbench-editor">
              <MaterialEditor
                material={material}
                onSave={save}
                onDraftChange={setLiveResumeText}
              />
              <div className="card export-panel resume-style-panel">
                <div>
                  <p className="section-kicker">APPLYEASE · RESUME STUDIO</p>
                  <h2>{t("builder.exportTitle")}</h2>
                  <p className="privacy-note">{t("builder.exportNote")}</p>
                </div>
                <div className="export-options">
                  <label>
                    {t("builder.name")}
                    <input
                      value={displayName}
                      maxLength={100}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder={t("builder.namePlaceholder")}
                    />
                  </label>
                  <label>
                    {t("builder.email")}
                    <input
                      type="email"
                      value={email}
                      maxLength={320}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder={t("builder.emailPlaceholder")}
                    />
                  </label>
                  <label>
                    {t("builder.phone")}
                    <input
                      type="tel"
                      value={phone}
                      maxLength={80}
                      onChange={(e) => setPhone(e.target.value)}
                      placeholder={t("builder.phonePlaceholder")}
                    />
                  </label>
                  <label>
                    {t("builder.location")}
                    <input
                      value={location}
                      maxLength={160}
                      onChange={(e) => setLocation(e.target.value)}
                      placeholder={t("builder.locationPlaceholder")}
                    />
                  </label>
                  <label>
                    {t("builder.linkedin")}
                    <input
                      type="url"
                      value={linkedinUrl}
                      maxLength={500}
                      onChange={(e) => setLinkedinUrl(e.target.value)}
                      placeholder={t("builder.linkedinPlaceholder")}
                    />
                  </label>
                  <label>
                    {t("builder.github")}
                    <input
                      type="url"
                      value={githubUrl}
                      maxLength={500}
                      onChange={(e) => setGithubUrl(e.target.value)}
                      placeholder={t("builder.githubPlaceholder")}
                    />
                  </label>
                </div>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={includeSources}
                    onChange={(e) => setIncludeSources(e.target.checked)}
                  />
                  {t("builder.includeSources")}
                </label>
                <div className="actions">
                  <button
                    disabled={profileBusy}
                    onClick={() => void persistProfile()}
                  >
                    {t("builder.saveProfile")}
                  </button>
                  <button
                    disabled={profileBusy}
                    onClick={() => void removeProfile()}
                  >
                    {t("builder.deleteProfile")}
                  </button>
                </div>
                {profileMessage && (
                  <p className="privacy-note" role="status">
                    {profileMessage}
                  </p>
                )}
                <div className="section-customizer">
                  <h3>{t("builder.sections")}</h3>
                  {sectionOrder.map((name, index) => (
                    <div className="section-row" key={name}>
                      <label className="inline-check">
                        <input
                          aria-label={t("builder.show", { name })}
                          type="checkbox"
                          checked={!hiddenSections.includes(name)}
                          onChange={() =>
                            setHiddenSections((items) =>
                              items.includes(name)
                                ? items.filter((item) => item !== name)
                                : [...items, name],
                            )
                          }
                        />
                        {name}
                      </label>
                      <div>
                        <button
                          aria-label={t("builder.up", { name })}
                          disabled={index === 0}
                          onClick={() => moveSection(name, -1)}
                        >
                          ↑
                        </button>
                        <button
                          aria-label={t("builder.down", { name })}
                          disabled={index === sectionOrder.length - 1}
                          onClick={() => moveSection(name, 1)}
                        >
                          ↓
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </aside>
            <section className="resume-workbench-preview">
              <details className="resume-audit-dock">
                <summary>
                  <span className="audit-summary-icon" aria-hidden="true">
                    ✓
                  </span>
                  <span className="audit-summary-copy">
                    <strong>{t("integrity.compactTitle")}</strong>
                    <small>
                      {t("integrity.compactSub", {
                        n: material.sources?.length || 0,
                      })}
                    </small>
                  </span>
                  <span
                    className={
                      material.fact_check_passed
                        ? "audit-summary-score pass"
                        : "audit-summary-score review"
                    }
                  >
                    {material.fact_check_passed && material.sources?.length
                      ? "100"
                      : material.fact_check_passed
                        ? "55"
                        : "0"}
                    <small>/100</small>
                  </span>
                  <span className="audit-summary-toggle">
                    {t("integrity.viewDetails")}
                  </span>
                </summary>
                <div className="resume-audit-details">
                  <ApplicationIntegrityGate material={material} />
                  <EvidenceTracing material={material} />
                </div>
              </details>
              {resumeAppearanceControls}
              <ResumePreview
                text={liveResumeText ?? material.text}
                displayName={displayName}
                contactLine={contactLine}
                contact={{ email, phone, location, linkedinUrl, githubUrl }}
                template={template}
                appearance={resumeAppearance}
                order={sectionOrder}
                hidden={hiddenSections}
              />
              <div className="resume-export-actions">
                <button
                  disabled={exportDisabled}
                  onClick={() => void exportCurrent("docx")}
                >
                  {exporting === "docx"
                    ? t("builder.exporting")
                    : t("builder.exportDocx")}
                </button>
                <button
                  disabled={exportDisabled}
                  onClick={() => void exportCurrent("pdf")}
                >
                  {exporting === "pdf"
                    ? t("builder.exporting")
                    : t("builder.exportPdf")}
                </button>
              </div>
              {!displayName.trim() && (
                <p className="export-name-hint">{t("builder.nameToExport")}</p>
              )}
              {!material.fact_check_passed && (
                <p className="warning" role="alert">
                  {t("builder.factCheckWarn")}
                </p>
              )}
            </section>
          </section>
        )}
        {material && material.material_type !== "resume" && (
          <MaterialEditor material={material} onSave={save} />
        )}
        {material && material.material_type !== "resume" && (
          <details className="resume-audit-dock material-audit-dock">
            <summary>
              <span className="audit-summary-icon" aria-hidden="true">
                ✓
              </span>
              <span className="audit-summary-copy">
                <strong>{t("integrity.compactTitle")}</strong>
                <small>
                  {t("integrity.compactSub", {
                    n: material.sources?.length || 0,
                  })}
                </small>
              </span>
              <span className="audit-summary-toggle">
                {t("integrity.viewDetails")}
              </span>
            </summary>
            <div className="resume-audit-details">
              <ApplicationIntegrityGate material={material} />
              <EvidenceTracing material={material} />
            </div>
          </details>
        )}
      </section>
    </main>
  );
}
