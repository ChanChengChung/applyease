import { useEffect, useState } from "react";
import {
  checkResourceHealth,
  completeResource,
  createExperienceDraft,
  getResearchPlan,
  getSavedResearchPlan,
  updateResearchPlan,
  deleteResearchPlan,
  getRecommendations,
  getSavedStarterPlan,
  refineStarterPlan,
  updateStarterPlan,
  submitResourceFeedback,
} from "../../services/resourceApi";
import type { ResourceFeedbackCategory } from "../../services/resourceApi";
import type {
  LearningResource,
  ResearchPlan,
  StarterPlan,
} from "../../types/resource";
import { useI18n, useT } from "../../i18n/LanguageProvider";
import { downloadStarterPlan } from "../../utils/starterPlanExport";
import { listJobs } from "../../services/jobApi";
import type { Job } from "../../types/job";

export function ResourcePlanPage({ initialJobId }: { initialJobId?: number }) {
  const [jobId, setJobId] = useState<number | null>(initialJobId || null);
  const [planSource, setPlanSource] = useState<"job" | "starter" | null>(
    initialJobId ? "job" : null,
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [goal, setGoal] = useState<"skills" | "project" | "interview">(
    "skills",
  );

  const [level, setLevel] = useState<
    "" | "beginner" | "intermediate" | "advanced"
  >("");

  const [weeklyHours, setWeeklyHours] = useState("3");
  const [weeks, setWeeks] = useState("2");
  const [learningStyle, setLearningStyle] = useState<
    "hands_on" | "guided" | "intensive"
  >("hands_on");

  const [freeOnly, setFreeOnly] = useState(false);

  const [items, setItems] = useState<LearningResource[]>([]);

  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [reflections, setReflections] = useState<Record<number, string>>({});
  const [drafted, setDrafted] = useState<Record<number, boolean>>({});
  const [reportingId, setReportingId] = useState<number | null>(null);
  const [feedbackCategory, setFeedbackCategory] =
    useState<ResourceFeedbackCategory>("broken_link");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackSaved, setFeedbackSaved] = useState<Record<number, boolean>>(
    {},
  );
  const [researchPlan, setResearchPlan] = useState<ResearchPlan | null>(null);
  const [editingResearch, setEditingResearch] = useState(false);
  const [researchDraft, setResearchDraft] = useState<ResearchPlan | null>(null);
  const [starterPlan, setStarterPlan] = useState<StarterPlan | null>(null);
  const [editingStarter, setEditingStarter] = useState(false);
  const [starterDraft, setStarterDraft] = useState<StarterPlan | null>(null);
  const [starterSaving, setStarterSaving] = useState(false);

  const t = useT();
  const { language } = useI18n();

  useEffect(() => {
    void listJobs()
      .then((rows) => {
        setJobs(rows);
      })
      .catch(() => setJobs([]));
  }, []);

  useEffect(() => {
    let active = true;
    void getSavedStarterPlan()
      .then((plan) => active && setStarterPlan(plan))
      .catch(() => active && setStarterPlan(null));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    // The selected role can change from Materials & forms without unmounting
    // this page. Treat the routed role as authoritative rather than retaining
    // the previous local selection.
    if (initialJobId !== undefined) {
      setJobId(initialJobId);
      setPlanSource("job");
    }
  }, [initialJobId]);
  useEffect(() => {
    // A starter plan is intentionally independent of any selected target
    // role. Cancelling this fetch when the source changes prevents a late job
    // response from replacing a newly generated saved-starter plan.
    if (planSource !== "job" || !jobId) {
      setResearchPlan(null);
      setEditingResearch(false);
      setResearchDraft(null);
      return;
    }
    let active = true;
    void getSavedResearchPlan(jobId)
      .then((plan) => {
        if (active) {
          setResearchPlan(plan);
          setLoaded(true);
        }
      })
      .catch(() => {
        if (active) setResearchPlan(null);
      });
    return () => {
      active = false;
    };
  }, [jobId, planSource]);
  const beginStarterEdit = () => {
    if (!starterPlan) return;
    setStarterDraft({ ...starterPlan, milestones: [...starterPlan.milestones] });
    setEditingStarter(true);
  };
  const cancelStarterEdit = () => {
    setStarterDraft(null);
    setEditingStarter(false);
  };
  const saveStarterEdit = async () => {
    if (!starterDraft) return;
    try {
      setStarterSaving(true);
      setError("");
      const saved = await updateStarterPlan(starterDraft.id, {
        focus: starterDraft.focus.trim(),
        headline: starterDraft.headline.trim(),
        first_action: starterDraft.first_action.trim(),
        milestones: starterDraft.milestones
          .map((step) => step.trim())
          .filter(Boolean),
      });
      setStarterPlan(saved);
      setStarterDraft(null);
      setEditingStarter(false);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : t("resource.starterSaveFailed"),
      );
    } finally {
      setStarterSaving(false);
    }
  };
  const beginResearchEdit = () => {
    if (!researchPlan) return;
    setResearchDraft({
      ...researchPlan,
      gaps: [...researchPlan.gaps],
      method: [...researchPlan.method],
      sources: researchPlan.sources.map((item) => ({ ...item })),
    });
    setEditingResearch(true);
  };
  const saveResearchEdit = async () => {
    if (!researchDraft) return;
    const sources = researchDraft.sources.filter(
      (source) => source.title.trim() && source.url.trim(),
    );
    try {
      setBusy(true);
      setError("");
      setResearchPlan(
        await updateResearchPlan(researchDraft.id, {
          profile_summary: researchDraft.profile_summary.trim(),
          gaps: researchDraft.gaps.map((x) => x.trim()).filter(Boolean),
          method: researchDraft.method.map((x) => x.trim()).filter(Boolean),
          sources,
        }),
      );
      setEditingResearch(false);
      setResearchDraft(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.failed"));
    } finally {
      setBusy(false);
    }
  };
  const removeResearchPlan = async () => {
    if (!researchPlan) return;
    try {
      setBusy(true);
      setError("");
      await deleteResearchPlan(researchPlan.id);
      setResearchPlan(null);
      setResearchDraft(null);
      setEditingResearch(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.failed"));
    } finally {
      setBusy(false);
    }
  };

  const load = async () => {
    if (planSource === "starter") {
      if (!starterPlan) {
        setError(t("resource.starterRequired"));
        return;
      }
      const weekly = Number(weeklyHours);
      const durationWeeks = Number(weeks);
      setError("");
      setBusy(true);
      try {
        const refined = await refineStarterPlan(starterPlan.id, {
          weekly_hours: weekly,
          weeks: durationWeeks,
          goal,
          learning_style: learningStyle,
          language,
        });
        setStarterPlan(refined);
        // The refined endpoint returns the new researched resources. Keep the
        // visible resource list in sync instead of leaving the old empty list.
        setItems(refined.resources);
        setResearchPlan(null);
        setDrafted({});
        setLoaded(true);
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : t("resource.failed"));
      } finally {
        setBusy(false);
      }
      return;
    }
    const id = jobId;
    if (!id) {
      setError(t("resource.invalidJobId"));
      return;
    }

    const weekly = Number(weeklyHours);
    const durationWeeks = Number(weeks);
    const hours = weekly * durationWeeks;

    if (
      !Number.isInteger(hours) ||
      hours < 1 ||
      hours > 200
    ) {
      setError(t("resource.invalidHours"));
      return;
    }

    setError("");
    setBusy(true);

    try {
      setItems(
        await getRecommendations(id, {
          level: level || undefined,
          max_total_hours: hours,
          free_only: freeOnly,
          limit: 12,
          goal,
          language,
        }),
      );
      setResearchPlan(
        await getResearchPlan({
          job_id: id,
          weekly_hours: weekly,
          weeks: durationWeeks,
          goal,
          learning_style: learningStyle,
          language,
        }),
      );
      setLoaded(true);
      setDrafted({});
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.failed"));
    } finally {
      setBusy(false);
    }
  };

  const toggle = async (item: LearningResource) => {
    setBusy(true);
    setError("");

    try {
      const updated = await completeResource(item.id, !item.completed);
      setItems((current) =>
        current.map((value) => (value.id === item.id ? updated : value)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.statusFailed"));
    } finally {
      setBusy(false);
    }
  };

  const createDraft = async (item: LearningResource) => {
    const reflection = (reflections[item.id] || "").trim();
    if (reflection.length < 10) {
      setError(t("resource.reflectionRequired"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createExperienceDraft(item.id, reflection);
      setDrafted((current) => ({ ...current, [item.id]: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.draftFailed"));
    } finally {
      setBusy(false);
    }
  };
  const checkHealth = async (item: LearningResource) => {
    setBusy(true);
    setError("");
    try {
      const updated = await checkResourceHealth(item.id);
      setItems((current) =>
        current.map((value) => (value.id === item.id ? updated : value)),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.checkLinkFailed"));
    } finally {
      setBusy(false);
    }
  };
  const openReport = (resourceId: number) => {
    setReportingId(resourceId);
    setFeedbackCategory("broken_link");
    setFeedbackMessage("");
    setError("");
  };
  const reportLink = async (item: LearningResource) => {
    const message = feedbackMessage.trim();
    if (message.length < 3) {
      setError(t("resource.feedbackPlaceholder"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      await submitResourceFeedback(item.id, feedbackCategory, message);
      setFeedbackSaved((current) => ({ ...current, [item.id]: true }));
      setReportingId(null);
      setFeedbackMessage("");
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.feedbackFailed"));
    } finally {
      setBusy(false);
    }
  };

  const plannedHours = Number(weeklyHours) * Number(weeks);

  return (
    <main className="product-page resource-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="page-wordmark">· RESOURCE PLAN</span>
          </p>
          <h1>{t("resource.hero.title")}</h1>
          <p className="sub">{t("resource.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-resource" aria-hidden="true">
          <span>✧</span>
        </div>
      </header>
      <section className="product-content">
        {starterPlan && (
          <section
            className="card saved-starter-plan"
            aria-label={t("resource.starterSavedTitle")}
          >
            <div className="saved-starter-heading">
              <p className="section-kicker">00 · STARTER PLAN</p>
              <h2>{t("resource.starterSavedTitle")}</h2>
              {editingStarter && starterDraft ? (
                <label>
                  {t("resource.starterHeadline")}
                  <textarea
                    value={starterDraft.headline}
                    onChange={(event) =>
                      setStarterDraft({ ...starterDraft, headline: event.target.value })
                    }
                  />
                </label>
              ) : (
                  <>
                    <p>{starterPlan.headline}</p>
                    <p className="starter-original-intent">
                      {t("resource.starterIntent", { intent: starterPlan.interest })}
                    </p>
                  </>
              )}
            </div>
            <div className="saved-starter-plan-action">
              <strong>{t("resource.starterFirstAction")}</strong>
              {editingStarter && starterDraft ? (
                <textarea
                  aria-label={t("resource.starterFirstAction")}
                  value={starterDraft.first_action}
                  onChange={(event) =>
                    setStarterDraft({
                      ...starterDraft,
                      first_action: event.target.value,
                    })
                  }
                />
              ) : (
                <span>{starterPlan.first_action}</span>
              )}
            </div>
            <ol className="saved-starter-milestones">
              {(editingStarter && starterDraft
                ? starterDraft.milestones
                : starterPlan.milestones
              ).map((step, index) => (
                <li key={`${index}-${step}`}>
                  {editingStarter && starterDraft ? (
                    <div className="starter-milestone-editor">
                      <textarea
                        aria-label={t("resource.starterMilestone", { n: index + 1 })}
                        value={step}
                        onChange={(event) => {
                          const milestones = [...starterDraft.milestones];
                          milestones[index] = event.target.value;
                          setStarterDraft({ ...starterDraft, milestones });
                        }}
                      />
                      <button
                        type="button"
                        className="icon-action danger-action"
                        aria-label={t("resource.removeMilestone")}
                        disabled={starterDraft.milestones.length <= 1}
                        onClick={() =>
                          setStarterDraft({
                            ...starterDraft,
                            milestones: starterDraft.milestones.filter(
                              (_, itemIndex) => itemIndex !== index,
                            ),
                          })
                        }
                      >
                        ×
                      </button>
                    </div>
                  ) : (
                    step
                  )}
                </li>
              ))}
            </ol>
            <div className="saved-starter-resources">
              {starterPlan.resources.map((item) => (
                <a
                  href={item.url}
                  target="_blank"
                  rel="noreferrer"
                  key={item.id}
                >
                  {item.title}
                  <span>{item.provider}</span>
                </a>
              ))}
            </div>
            <div className="saved-starter-controls">
              {editingStarter && starterDraft ? (
                <>
                  <button
                    type="button"
                    className="secondary-action"
                    onClick={() =>
                      setStarterDraft({
                        ...starterDraft,
                        milestones: [...starterDraft.milestones, ""],
                      })
                    }
                  >
                    + {t("resource.addMilestone")}
                  </button>
                  <button type="button" onClick={() => void saveStarterEdit()} disabled={starterSaving}>
                    {starterSaving ? t("resource.starterSaving") : t("resource.starterSave")}
                  </button>
                  <button type="button" className="secondary-action" onClick={cancelStarterEdit}>
                    {t("resource.starterCancel")}
                  </button>
                </>
              ) : (
                <>
                  <button type="button" onClick={beginStarterEdit}>
                    {t("resource.starterEdit")}
                  </button>
                  <button
                    type="button"
                    className="saved-starter-export"
                    onClick={() => downloadStarterPlan(starterPlan)}
                  >
                    {t("starter.export")}
                  </button>
                </>
              )}
            </div>
          </section>
        )}
        <div className="card learning-planner">
          <div className="planner-heading">
            <div>
              <p className="section-kicker">01 · MY LEARNING PLAN</p>
              <h2>{t("resource.learningTitle")}</h2>
              <p className="planner-intro">{t("resource.learningSub")}</p>
            </div>
          </div>
          <div className="planner-source-step">
            <p className="control-label">{t("resource.sourceTitle")}</p>
            <p>{t("resource.sourceHelp")}</p>
            <div className="planner-source-options">
              <button
                type="button"
                className={planSource === "job" ? "active" : ""}
                disabled={!jobs.length}
                onClick={() => setPlanSource("job")}
              >
                <strong>{t("resource.source.job")}</strong>
                <small>{t("resource.source.jobHelp")}</small>
              </button>
              <button
                type="button"
                className={planSource === "starter" ? "active" : ""}
                disabled={!starterPlan}
                onClick={() => {
                  setPlanSource("starter");
                  setResearchPlan(null);
                  setResearchDraft(null);
                  setEditingResearch(false);
                }}
              >
                <strong>{t("resource.source.starter")}</strong>
                <small>{t("resource.source.starterHelp")}</small>
              </button>
            </div>
            {planSource === "job" && (
              <label className="planner-source-picker">
                {t("resource.chooseJob")}
                <select
                  aria-label={t("resource.chooseJob")}
                  value={jobId ?? ""}
                  onChange={(event) => setJobId(Number(event.target.value) || null)}
                >
                  <option value="">{t("resource.chooseJobPlaceholder")}</option>
                  {jobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.company} · {job.title}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {planSource === "starter" && starterPlan && (
              <div className="planner-starter-context">
                <strong>{starterPlan.headline}</strong>
                <span>{t("resource.starterIntent", { intent: starterPlan.interest })}</span>
              </div>
            )}
          </div>
          <div className="planner-preferences">
            <div className="planner-choice-group planner-goal-group">
              <p className="control-label">{t("resource.goal")}</p>
              <div className="goal-options">
                {(["skills", "project", "interview"] as const).map((value) => (
                  <button
                    type="button"
                    className={goal === value ? "active" : ""}
                    onClick={() => setGoal(value)}
                    key={value}
                  >
                    {t(`resource.goal.${value}`)}
                  </button>
                ))}
              </div>
            </div>
            <div className="planner-choice-group">
              <p className="control-label">{t("resource.learningStyle")}</p>
              <div className="learning-style-options">
                {(["hands_on", "guided", "intensive"] as const).map((value) => (
                  <button
                    type="button"
                    className={learningStyle === value ? "active" : ""}
                    onClick={() => setLearningStyle(value)}
                    key={value}
                  >
                    <strong>{t(`resource.style.${value}`)}</strong>
                    <small>{t(`resource.style.${value}.sub`)}</small>
                  </button>
                ))}
              </div>
            </div>
            <div className="planner-details-grid">
              <label>
                {t("resource.level")}
                <select
                  aria-label={t("resource.level")}
                  value={level}
                  onChange={(e) => setLevel(e.target.value as typeof level)}
                >
                  <option value="">{t("resource.level.all")}</option>
                  <option value="beginner">{t("resource.level.beginner")}</option>
                  <option value="intermediate">{t("resource.level.intermediate")}</option>
                  <option value="advanced">{t("resource.level.advanced")}</option>
                </select>
              </label>
              <label>
                {t("resource.weeklyHours")}
                <select value={weeklyHours} onChange={(event) => setWeeklyHours(event.target.value)}>
                  <option value="2">2</option>
                  <option value="3">3</option>
                  <option value="5">5</option>
                  <option value="8">8</option>
                  <option value="12">12</option>
                </select>
              </label>
              <label>
                {t("resource.planLength")}
                <select value={weeks} onChange={(event) => setWeeks(event.target.value)}>
                  <option value="1">1</option>
                  <option value="2">2</option>
                  <option value="4">4</option>
                  <option value="6">6</option>
                  <option value="8">8</option>
                </select>
              </label>
              <label className="planner-free-choice">
                <input
                  type="checkbox"
                  aria-label={t("resource.freeOnly")}
                  checked={freeOnly}
                  onChange={(e) => setFreeOnly(e.target.checked)}
                />
                <span><strong>{t("resource.freeOnly")}</strong><small>{t("resource.freeOnlySub")}</small></span>
              </label>
            </div>
            <div className="planner-generate-row">
              <span>{t("resource.timeBudgetSummary", { n: plannedHours })}</span>
              <button
                disabled={
                  busy || !planSource ||
                  (planSource === "job" && !jobId) ||
                  (planSource === "starter" && !starterPlan)
                }
                onClick={() => void load()}
              >
                {busy ? t("resource.generating") : t("resource.generate")}
              </button>
            </div>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </div>

        {loaded && researchPlan && (
          <section
            className="research-plan card"
            aria-label={t("research.kicker")}
          >
            <p className="section-kicker">{t("research.kicker")}</p>
            <div className="research-actions">
              <button
                type="button"
                className="planner-link"
                onClick={beginResearchEdit}
              >
                {t("research.edit")}
              </button>
              <button
                type="button"
                className="danger-link"
                onClick={() => void removeResearchPlan()}
              >
                {t("research.delete")}
              </button>
            </div>
            {editingResearch && researchDraft ? (
              <>
                <label>
                  {t("research.summary")}
                  <textarea
                    value={researchDraft.profile_summary}
                    onChange={(e) =>
                      setResearchDraft({
                        ...researchDraft,
                        profile_summary: e.target.value,
                      })
                    }
                  />
                </label>
                <label>
                  {t("research.gaps")}
                  <textarea
                    value={researchDraft.gaps.join("\n")}
                    onChange={(e) =>
                      setResearchDraft({
                        ...researchDraft,
                        gaps: e.target.value.split("\n"),
                      })
                    }
                  />
                </label>
                <label>
                  {t("research.method")}
                  <textarea
                    value={researchDraft.method.join("\n")}
                    onChange={(e) =>
                      setResearchDraft({
                        ...researchDraft,
                        method: e.target.value.split("\n"),
                      })
                    }
                  />
                </label>
                <label>
                  {t("research.sources")}
                  <textarea
                    value={researchDraft.sources
                      .map((source) => `${source.title} | ${source.url}`)
                      .join("\n")}
                    onChange={(e) =>
                      setResearchDraft({
                        ...researchDraft,
                        sources: e.target.value.split("\n").map((line) => {
                          const [title, ...rest] = line.split("|");
                          return {
                            title: title.trim(),
                            url: rest.join("|").trim(),
                          };
                        }),
                      })
                    }
                  />
                </label>
                <div className="research-actions">
                  <button
                    type="button"
                    disabled={busy || !researchDraft.profile_summary.trim()}
                    onClick={() => void saveResearchEdit()}
                  >
                    {t("research.save")}
                  </button>
                  <button
                    type="button"
                    className="planner-link"
                    onClick={() => {
                      setEditingResearch(false);
                      setResearchDraft(null);
                    }}
                  >
                    {t("shared.cancel")}
                  </button>
                </div>
              </>
            ) : (
              <>
                <h2>{researchPlan.profile_summary}</h2>
                {researchPlan.used_fallback && (
                  <p className="warning">{t("research.fallback")}</p>
                )}
                <div>
                  <strong>{t("research.gaps")}</strong>
                  <ul>
                    {researchPlan.gaps.map((gap) => (
                      <li key={gap}>{gap}</li>
                    ))}
                  </ul>
                </div>
                <div>
                  <strong>{t("research.method")}</strong>
                  <ol>
                    {researchPlan.method.map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ol>
                </div>
                <div className="starter-resources">
                  {researchPlan.sources.map((source) => (
                    <a
                      key={source.url}
                      href={source.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      <strong>{source.title}</strong>
                      <small>{t("research.source")}</small>
                    </a>
                  ))}
                </div>
              </>
            )}
          </section>
        )}
        {loaded && items.length === 0 && (
          <div className="empty">
            <p>{t("resource.empty")}</p>
            <small>{t("resource.emptyHint")}</small>
          </div>
        )}

        {items.map((item) => (
          <article
            className={`card resource-card ${item.completed ? "resource-completed" : ""}`}
            key={item.id}
          >
            <div className="card-header">
              <div>
                <h2>{item.title}</h2>
                <span>
                  {item.provider} · {item.difficulty} ·{" "}
                  {t("resource.duration", { n: item.duration_hours })}
                </span>
              </div>
              <button disabled={busy} onClick={() => void toggle(item)}>
                {item.completed
                  ? t("resource.completed")
                  : t("resource.markDone")}
              </button>
            </div>
            <p>{item.description}</p>
            <p>
              {t("resource.reason", {
                reason: item.recommendation_reason || "—",
              })}
            </p>
            <p>{t("resource.matchScore", { score: item.match_score ?? 0 })}</p>
            <a href={item.url} target="_blank" rel="noreferrer">
              {t("resource.open")}
            </a>
            <div className="actions">
              <button disabled={busy} onClick={() => void checkHealth(item)}>
                {busy ? t("resource.checkingLink") : t("resource.checkLink")}
              </button>
              <button
                disabled={busy}
                onClick={() =>
                  reportingId === item.id
                    ? setReportingId(null)
                    : openReport(item.id)
                }
              >
                {reportingId === item.id
                  ? t("resource.cancelReport")
                  : t("resource.reportIssue")}
              </button>
              {item.link_status && item.link_status !== "unchecked" && (
                <small
                  className={
                    item.link_status === "healthy" ? "success" : "warning"
                  }
                  role="status"
                >
                  {item.link_status === "healthy"
                    ? t("resource.linkHealthy")
                    : t("resource.linkBroken")}
                </small>
              )}
            </div>
            {reportingId === item.id && (
              <div className="resource-draft">
                <label>
                  {t("resource.feedbackCategory")}
                  <select
                    aria-label={t("resource.feedbackCategory")}
                    value={feedbackCategory}
                    onChange={(event) =>
                      setFeedbackCategory(
                        event.target.value as ResourceFeedbackCategory,
                      )
                    }
                  >
                    <option value="broken_link">
                      {t("resource.feedback.broken")}
                    </option>
                    <option value="outdated_content">
                      {t("resource.feedback.outdated")}
                    </option>
                    <option value="other">
                      {t("resource.feedback.other")}
                    </option>
                  </select>
                </label>
                <label>
                  {t("resource.feedbackMessage")}
                  <textarea
                    aria-label={t("resource.feedbackMessage")}
                    value={feedbackMessage}
                    maxLength={1000}
                    placeholder={t("resource.feedbackPlaceholder")}
                    onChange={(event) => setFeedbackMessage(event.target.value)}
                  />
                </label>
                <button
                  disabled={busy || feedbackMessage.trim().length < 3}
                  onClick={() => void reportLink(item)}
                >
                  {t("resource.submitFeedback")}
                </button>
              </div>
            )}
            {feedbackSaved[item.id] && (
              <p className="success" role="status">
                {t("resource.feedbackSaved")}
              </p>
            )}
            <div className="tags">
              {item.skills.map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
            <h3>{t("resource.project", { title: item.project.title })}</h3>
            <p>{item.project.task}</p>
            <strong>{t("resource.deliverable")}</strong>
            <ul>
              {item.project.deliverables.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
            <strong>{t("resource.criteria")}</strong>
            <ul>
              {item.project.completion_criteria.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
            <small>
              {t("resource.cvBullet", {
                bullet: item.project.cv_bullet_template,
              })}
            </small>
            {item.completed && (
              <div className="resource-draft">
                <h3>{t("resource.draftTitle")}</h3>
                <p className="privacy-note">{t("resource.draftHelp")}</p>
                <label>
                  {`${t("resource.reflection")}：${item.title}`}
                  <textarea
                    aria-label={`${t("resource.reflection")}：${item.title}`}
                    value={reflections[item.id] || ""}
                    maxLength={3000}
                    placeholder={t("resource.reflectionPlaceholder")}
                    onChange={(event) =>
                      setReflections((current) => ({
                        ...current,
                        [item.id]: event.target.value,
                      }))
                    }
                  />
                </label>
                <button
                  disabled={
                    busy ||
                    drafted[item.id] ||
                    (reflections[item.id] || "").trim().length < 10
                  }
                  onClick={() => void createDraft(item)}
                >
                  {drafted[item.id]
                    ? t("resource.draftCreated")
                    : t("resource.createDraft")}
                </button>
                {drafted[item.id] && (
                  <p className="success" role="status">
                    {t("resource.draftCreatedHelp")}
                  </p>
                )}
              </div>
            )}
          </article>
        ))}
      </section>
    </main>
  );
}
