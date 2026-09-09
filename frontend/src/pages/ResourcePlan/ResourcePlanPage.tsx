import { useEffect, useState } from "react";
import {
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
} from "../../services/resourceApi";
import * as resourceApi from "../../services/resourceApi";
import type {
  LearningResource,
  ResearchPlan,
  StarterPlan,
} from "../../types/resource";
import { useI18n, useT } from "../../i18n/LanguageProvider";
import { downloadStarterPlan } from "../../utils/starterPlanExport";
import { detectContentLanguage } from "../../utils/contentLanguage";
import { listJobs } from "../../services/jobApi";
import type { Job } from "../../types/job";
import { listMaterials } from "../../services/materialApi";
import { getLatestApplication } from "../../services/applicationApi";
import type { Material } from "../../types/material";
import type { Application } from "../../types/application";
import reinforcementPlanDocument from "../../assets/reinforcement-plan-document.png";

type StarterSectionKey = "foundation" | "practice" | "reflection";
type RoleFocus = "evidence" | "skills" | "materials";
const ROLE_FOCUS_OPTIONS: RoleFocus[] = ["evidence", "skills", "materials"];
const STARTER_SECTION_KEYS: StarterSectionKey[] = ["foundation", "practice", "reflection"];

function fallbackStarterSections(milestones: string[]): Record<StarterSectionKey, string[]> {
  const first = Math.max(1, Math.ceil(milestones.length / 3));
  const second = Math.max(first + 1, Math.ceil((milestones.length * 2) / 3));
  return {
    foundation: milestones.slice(0, first),
    practice: milestones.slice(first, second),
    reflection: milestones.slice(second),
  };
}

function getStarterSections(plan: StarterPlan): Record<StarterSectionKey, string[]> {
  const saved = plan.milestone_sections;
  if (saved && STARTER_SECTION_KEYS.some((key) => saved[key]?.length)) {
    return {
      foundation: [...(saved.foundation || [])],
      practice: [...(saved.practice || [])],
      reflection: [...(saved.reflection || [])],
    };
  }
  return fallbackStarterSections(plan.milestones);
}

function resourceHostname(url: string, fallback: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "") || fallback;
  } catch {
    return fallback;
  }
}

function concisePlanSummary(value: string): string {
  const text = value.replace(/\s+/g, " ").trim();
  if (text.length <= 220) return text;
  const firstClause = text.split(/[；;，,]/)[0]?.trim();
  const compact = firstClause && firstClause.length >= 20 ? firstClause : text;
  return `${compact.slice(0, 220).trimEnd()}…`;
}

function resourceMatchLevel(item: LearningResource): "very_high" | "high" | "medium" | "low" {
  if (item.match_level) return item.match_level;
  // Older API payloads may omit the band. Treat a missing/legacy zero as a
  // conservative baseline, not as a failed match.
  const score = item.match_score && item.match_score > 0 ? item.match_score : 50;
  if (score >= 80) return "very_high";
  if (score >= 60) return "high";
  if (score >= 40) return "medium";
  return "low";
}

function loadResearchHistory(jobId: number, fallback: ResearchPlan[]): Promise<ResearchPlan[]> {
  try {
    const loader = resourceApi.listResearchPlans;
    if (typeof loader === "function") {
      return loader(jobId).catch(() => fallback);
    }
  } catch {
    // Older clients/tests may not expose the optional history endpoint.
  }
  return Promise.resolve(fallback);
}

export function ResourcePlanPage({
  initialJobId,
  onCreateStarterPlan,
}: {
  initialJobId?: number;
  onCreateStarterPlan?: () => void;
}) {
  const [jobId, setJobId] = useState<number | null>(initialJobId || null);
  const [planSource, setPlanSource] = useState<"job" | "starter" | null>(
    initialJobId ? "job" : null,
  );
  const [jobs, setJobs] = useState<Job[]>([]);
  const [roleMaterials, setRoleMaterials] = useState<Material[]>([]);
  const [roleApplication, setRoleApplication] = useState<Application | null>(null);
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
  const [roleFocuses, setRoleFocuses] = useState<RoleFocus[]>([
    "evidence",
    "skills",
    "materials",
  ]);

  const [items, setItems] = useState<LearningResource[]>([]);

  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [draftingId, setDraftingId] = useState<number | null>(null);
  const [reflections, setReflections] = useState<Record<number, string>>({});
  const [drafted, setDrafted] = useState<Record<number, boolean>>({});
  const [researchPlan, setResearchPlan] = useState<ResearchPlan | null>(null);
  const [researchHistory, setResearchHistory] = useState<ResearchPlan[]>([]);
  const [selectedResearchId, setSelectedResearchId] = useState<number | null>(null);
  const [editingResearch, setEditingResearch] = useState(false);
  const [researchDraft, setResearchDraft] = useState<ResearchPlan | null>(null);
  const [starterPlan, setStarterPlan] = useState<StarterPlan | null>(null);
  const [starterPlans, setStarterPlans] = useState<StarterPlan[]>([]);
  const [editingStarter, setEditingStarter] = useState(false);
  const [starterDraft, setStarterDraft] = useState<StarterPlan | null>(null);
  const [activeStarterSection, setActiveStarterSection] =
    useState<StarterSectionKey>("foundation");
  const [starterSaving, setStarterSaving] = useState(false);

  const t = useT();
  const { language: systemLanguage } = useI18n();

  useEffect(() => {
    void listJobs()
      .then((rows) => {
        setJobs(rows);
      })
      .catch(() => setJobs([]));
  }, []);

  useEffect(() => {
    let active = true;
    const loadPlans =
      typeof resourceApi.listStarterPlans === "function"
        ? resourceApi.listStarterPlans().catch(() => getSavedStarterPlan().then((plan) => [plan]))
        : getSavedStarterPlan().then((plan) => [plan]);
    void loadPlans
      .then((plans) => {
        if (!active) return;
        setStarterPlans(plans);
        setStarterPlan(plans[0] || null);
      })
      .catch(() => active && setStarterPlan(null));
    return () => {
      active = false;
    };
  }, []);

  const selectStarterPlan = (plan: StarterPlan) => {
    setStarterPlan(plan);
    setEditingStarter(false);
    setStarterDraft(null);
    setPlanSource("starter");
    setResearchPlan(null);
    setResearchHistory([]);
    setSelectedResearchId(null);
    setResearchDraft(null);
  };

  const removeStarterPlan = async () => {
    if (!starterPlan) return;
    try {
      setStarterSaving(true);
      await resourceApi.deleteStarterPlan(starterPlan.id);
      const remaining = starterPlans.filter((plan) => plan.id !== starterPlan.id);
      setStarterPlans(remaining);
      setStarterPlan(remaining[0] || null);
      if (!remaining.length) setPlanSource(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("resource.starterDeleteFailed"));
    } finally {
      setStarterSaving(false);
    }
  };

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
      setResearchHistory([]);
      setSelectedResearchId(null);
      setEditingResearch(false);
      setResearchDraft(null);
      return;
    }
    let active = true;
    void getSavedResearchPlan(jobId)
      .then((plan) => {
        if (active) {
          setResearchPlan(plan);
          if (plan.focuses?.length) setRoleFocuses(plan.focuses);
          setSelectedResearchId(null);
          void loadResearchHistory(jobId, [plan]).then(
            (history) => active && setResearchHistory(history),
          );
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

  useEffect(() => {
    if (planSource !== "job" || !jobId) {
      setRoleMaterials([]);
      setRoleApplication(null);
      return;
    }
    let active = true;
    setRoleMaterials([]);
    setRoleApplication(null);
    // These records are the user's existing application workspace for the
    // selected role.  A role may legitimately have no generated material or
    // no imported questions yet, so each request has an empty-state fallback.
    void Promise.all([
      listMaterials(jobId).catch(() => [] as Material[]),
      getLatestApplication(jobId).catch(() => null),
    ]).then(([materials, application]) => {
      if (!active) return;
      setRoleMaterials(materials);
      setRoleApplication(application);
    });
    return () => {
      active = false;
    };
  }, [jobId, planSource]);
  const beginStarterEdit = () => {
    if (!starterPlan) return;
    const sections = getStarterSections(starterPlan);
    setStarterDraft({
      ...starterPlan,
      milestones: STARTER_SECTION_KEYS.flatMap((key) => sections[key]),
      milestone_sections: sections,
    });
    setActiveStarterSection("foundation");
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
        milestones: STARTER_SECTION_KEYS.flatMap((key) =>
          (starterDraft.milestone_sections?.[key] || [])
            .map((step) => step.trim())
            .filter(Boolean),
        ),
        milestone_sections: {
          foundation: (starterDraft.milestone_sections?.foundation || [])
            .map((step) => step.trim())
            .filter(Boolean),
          practice: (starterDraft.milestone_sections?.practice || [])
            .map((step) => step.trim())
            .filter(Boolean),
          reflection: (starterDraft.milestone_sections?.reflection || [])
            .map((step) => step.trim())
            .filter(Boolean),
        },
      });
      setStarterPlan(saved);
      setStarterPlans((plans) => plans.map((plan) => (plan.id === saved.id ? saved : plan)));
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
      setResearchHistory((history) => history.filter((item) => item.id !== researchPlan.id));
      setSelectedResearchId(null);
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
          // A saved starter plan keeps the language of its original intent;
          // refinement must not silently switch to the UI locale.
          language: detectContentLanguage(starterPlan.interest),
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

    // A role-driven plan is specifically for closing evidence gaps.  Keep the
    // old goal/style controls for saved starter plans, while using stable
    // role-focused defaults for the replacement role workspace.
    const effectiveGoal = planSource === "job" ? "skills" : goal;
    const effectiveLearningStyle = planSource === "job" ? "guided" : learningStyle;

    try {
      setItems(
        await getRecommendations(id, {
          level: level || undefined,
          max_total_hours: hours,
          free_only: freeOnly,
          limit: 12,
          goal: effectiveGoal,
          language: systemLanguage,
        }),
      );
      const generated = await getResearchPlan({
          job_id: id,
          weekly_hours: weekly,
          weeks: durationWeeks,
          goal: effectiveGoal,
          learning_style: effectiveLearningStyle,
          language: systemLanguage,
          ...(roleFocuses.length === ROLE_FOCUS_OPTIONS.length ? {} : { focuses: roleFocuses }),
        });
      setResearchPlan(generated);
      setResearchHistory(await loadResearchHistory(id, [generated]));
      // Newly generated plans open once so the user can review the result;
      // older plans restored from history remain collapsed until clicked.
      setSelectedResearchId(generated.id);
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
    setDraftingId(item.id);
    setError("");
    try {
      await createExperienceDraft(item.id, reflection);
      setDrafted((current) => ({ ...current, [item.id]: true }));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("resource.draftFailed"));
    } finally {
      setDraftingId(null);
    }
  };

  const starterSectionData = starterPlan
    ? getStarterSections(editingStarter && starterDraft ? starterDraft : starterPlan)
    : null;
  const starterSections = starterSectionData
    ? STARTER_SECTION_KEYS.map((key) => ({
        key,
        title: t(`resource.starterSection.${key}`),
        items: starterSectionData[key],
      }))
    : [];
  const selectedJob = jobId ? jobs.find((job) => job.id === jobId) : undefined;
  const selectedResume = roleMaterials.find((item) => item.material_type === "resume");
  const selectedCoverLetter = roleMaterials.find(
    (item) => item.material_type === "cover_letter",
  );

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
        {starterPlan && planSource === "starter" && (
          <section
            className="card saved-starter-plan"
            aria-label={t("resource.starterSavedTitle")}
          >
            <div className="saved-starter-heading">
              <p className="section-kicker">00 · STARTER PLAN</p>
              <div className="starter-plan-header-row">
                <h2>{t("resource.starterSavedTitle")}</h2>
                <div className="starter-plan-management">
                  {starterPlans.length > 1 && (
                    <select
                      aria-label={t("resource.starterPlanSelect")}
                      value={starterPlan.id}
                      onChange={(event) => {
                        const selected = starterPlans.find(
                          (plan) => plan.id === Number(event.target.value),
                        );
                        if (selected) selectStarterPlan(selected);
                      }}
                    >
                      {starterPlans.map((plan) => (
                        <option value={plan.id} key={plan.id}>
                          {plan.interest.slice(0, 48)}
                        </option>
                      ))}
                    </select>
                  )}
                  {onCreateStarterPlan && (
                    <button type="button" className="secondary-action" onClick={onCreateStarterPlan}>
                      + {t("resource.starterNew")}
                    </button>
                  )}
                  <button type="button" className="danger-link" onClick={() => void removeStarterPlan()} disabled={starterSaving}>
                    {t("resource.starterDelete")}
                  </button>
                </div>
              </div>
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
                    <div className="starter-original-intent">
                      <span className="starter-intent-label">
                        {t("resource.starterIntentLabel")}
                      </span>
                      <span>{starterPlan.interest}</span>
                    </div>
                  </>
              )}
            </div>
            <div className="saved-starter-plan-action starter-first-action">
              <span className="starter-section-label">{t("resource.starterFirstAction")}</span>
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
            <div className="saved-starter-milestones">
              {starterSections
                .filter((section) => editingStarter || section.items.length > 0)
                .map((section) => (
                <section
                  className={`starter-milestone-section ${editingStarter && activeStarterSection === section.key ? "selected" : ""}`}
                  key={section.key}
                  onClick={() => editingStarter && setActiveStarterSection(section.key)}
                  tabIndex={editingStarter ? 0 : undefined}
                  onKeyDown={(event) => {
                    if (editingStarter && (event.key === "Enter" || event.key === " ")) {
                      event.preventDefault();
                      setActiveStarterSection(section.key);
                    }
                  }}
                >
                  <h3>{section.title}</h3>
                  <ol>
                  {section.items.map((step, index) => (
                    <li key={`${section.key}-${index}`}>
                  {editingStarter && starterDraft && activeStarterSection === section.key ? (
                    <div className="starter-milestone-editor">
                      <textarea
                        aria-label={`${section.title} ${t("resource.starterMilestone", { n: index + 1 })}`}
                        value={step}
                        onChange={(event) => {
                          const sections = getStarterSections(starterDraft);
                          sections[section.key][index] = event.target.value;
                          setStarterDraft({
                            ...starterDraft,
                            milestone_sections: sections,
                            milestones: STARTER_SECTION_KEYS.flatMap((key) => sections[key]),
                          });
                        }}
                      />
                      <button
                        type="button"
                        className="icon-action danger-action"
                        aria-label={t("resource.removeMilestone")}
                        disabled={section.items.length <= 1 && STARTER_SECTION_KEYS.every((key) => (starterDraft.milestone_sections?.[key] || []).length === 0)}
                        onClick={() =>
                          (() => {
                            const sections = getStarterSections(starterDraft);
                            sections[section.key] = sections[section.key].filter((_, itemIndex) => itemIndex !== index);
                            setStarterDraft({
                              ...starterDraft,
                              milestone_sections: sections,
                              milestones: STARTER_SECTION_KEYS.flatMap((key) => sections[key]),
                            });
                          })()
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
                </section>
              ))}
            </div>
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
                      (() => {
                        const sections = getStarterSections(starterDraft);
                        sections[activeStarterSection] = [...sections[activeStarterSection], ""];
                        setStarterDraft({
                          ...starterDraft,
                          milestone_sections: sections,
                          milestones: STARTER_SECTION_KEYS.flatMap((key) => sections[key]),
                        });
                      })()
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
              <p className="section-kicker">{t("resource.learningKicker")}</p>
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
                onClick={() => {
                  setPlanSource("job");
                  setLoaded(false);
                  setItems([]);
                  setResearchHistory([]);
                  setSelectedResearchId(null);
                }}
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
                  setLoaded(false);
                  setItems([]);
                  setResearchPlan(null);
                  setResearchHistory([]);
                  setSelectedResearchId(null);
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
                  onChange={(event) => {
                    setJobId(Number(event.target.value) || null);
                    setLoaded(false);
                    setItems([]);
                    setResearchPlan(null);
                    setResearchHistory([]);
                    setSelectedResearchId(null);
                  }}
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
            {planSource === "job" && selectedJob && (
              <section className="planner-role-materials" aria-label={t("resource.roleMaterialsTitle")}>
                <div className="planner-role-materials-heading">
                  <div>
                    <p className="section-kicker">{t("resource.roleMaterialsKicker")}</p>
                    <h3>{t("resource.roleMaterialsTitle")}</h3>
                    <p>{selectedJob.company} · {selectedJob.title}</p>
                  </div>
                  <span>{t("resource.roleMaterialsHelp")}</span>
                </div>
                <div className="planner-role-material-grid">
                  <article className={`planner-role-material ${selectedResume ? "available" : "missing"}`}>
                    <strong>{t("resource.roleResume")}</strong>
                    <span>{selectedResume ? t("resource.roleAvailable") : t("resource.roleMissing")}</span>
                    {selectedResume && <p>{selectedResume.text}</p>}
                  </article>
                  <article className={`planner-role-material ${selectedCoverLetter ? "available" : "missing"}`}>
                    <strong>{t("resource.roleCoverLetter")}</strong>
                    <span>{selectedCoverLetter ? t("resource.roleAvailable") : t("resource.roleMissing")}</span>
                    {selectedCoverLetter && <p>{selectedCoverLetter.text}</p>}
                  </article>
                </div>
                <article className="planner-role-questions">
                  <strong>{t("resource.roleQuestions")}</strong>
                  {roleApplication?.questions.length ? (
                    <ol>
                      {roleApplication.questions.map((question, index) => (
                        <li key={question.id || `${question.question}-${index}`}>{question.question}</li>
                      ))}
                    </ol>
                  ) : (
                    <span>{t("resource.roleQuestionsMissing")}</span>
                  )}
                </article>
              </section>
            )}
          </div>
          <div className="planner-preferences">
            {planSource === "job" ? (
              <section className="planner-role-focus">
                <p className="control-label">{t("resource.roleFocusTitle")}</p>
                <p>{t("resource.roleFocusHelp")}</p>
                <div className="planner-role-focus-points">
                  {ROLE_FOCUS_OPTIONS.map((focus) => (
                    <button
                      type="button"
                      className={roleFocuses.includes(focus) ? "active" : ""}
                      aria-pressed={roleFocuses.includes(focus)}
                      key={focus}
                      onClick={() =>
                        setRoleFocuses((current) =>
                          current.includes(focus)
                            ? current.filter((value) => value !== focus)
                            : [...current, focus],
                        )
                      }
                    >
                      {t(`resource.roleFocus${focus === "evidence" ? "Evidence" : focus === "skills" ? "Practice" : "Review"}`)}
                    </button>
                  ))}
                </div>
                {!roleFocuses.length && <small className="planner-role-focus-warning">{t("resource.roleFocusRequired")}</small>}
              </section>
            ) : (
              <>
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
              </>
            )}
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
              <button
                disabled={
                  busy || !planSource ||
                  (planSource === "job" && !jobId) ||
                  (planSource === "starter" && !starterPlan) ||
                  (planSource === "job" && !roleFocuses.length)
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

        {loaded && researchHistory.length > 0 && (
          <section className="research-history card" aria-label={t("research.historyTitle")}>
            <div className="research-history-heading">
              <div>
                <p className="section-kicker">02 · PLAN HISTORY</p>
                <h2>{t("research.historyTitle")}</h2>
                <p>{t("research.historyHelp")}</p>
              </div>
              <span className="research-history-count">{t("research.historyCount", { n: researchHistory.length })}</span>
            </div>
            <div className="research-history-grid">
              {researchHistory.map((plan, index) => (
                <button
                  type="button"
                  className={`research-history-card ${selectedResearchId === plan.id ? "selected" : ""}`}
                  key={plan.id}
                  onClick={() => {
                    setResearchPlan(plan);
                    setSelectedResearchId(plan.id);
                    setEditingResearch(false);
                    setResearchDraft(null);
                  }}
                >
                  <span className="research-history-preview">
                    <img src={reinforcementPlanDocument} alt="" />
                    <strong>{t("research.version", { n: researchHistory.length - index })}</strong>
                  </span>
                  <span className="research-history-card-meta">
                    <strong>{t("research.version", { n: researchHistory.length - index })}</strong>
                    <small>{new Date(plan.updated_at).toLocaleDateString()}</small>
                  </span>
                  <span className="research-history-hover">{t("research.previewLabel")}: {concisePlanSummary(plan.profile_summary)}</span>
                </button>
              ))}
            </div>
          </section>
        )}
        {loaded && researchPlan && selectedResearchId === researchPlan.id && (
          <section
            className="research-plan card"
            aria-label={t("research.kicker")}
          >
            <p className="section-kicker">{t("research.kicker")}</p>
            <div className="research-plan-provenance" role="status">
              <span>{t("research.starterSource")}</span>
              <strong>
                {researchPlan.starter_plan_interest ||
                  researchPlan.starter_plan_headline ||
                  t("research.unlinkedStarter")}
              </strong>
            </div>
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
                <div className="research-plan-summary">
                  <span>{t("research.planSummary")}</span>
                  <p title={researchPlan.profile_summary}>
                    {concisePlanSummary(researchPlan.profile_summary)}
                  </p>
                </div>
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
        {items.map((item) => (
          <article
            className={`card resource-card ${item.completed ? "resource-completed" : ""}`}
            key={item.id}
          >
            <div className="card-header">
              <div>
                <h2>{item.title}</h2>
                <div className="resource-meta" aria-label={t("resource.resourceDetails")}>
                  <span>
                    <strong>{t("resource.sourceUrl")}:</strong>{" "}
                    {resourceHostname(item.url, item.provider)}
                  </span>
                  <span>
                    <strong>{t("resource.completionTime")}:</strong>{" "}
                    {t("resource.duration", { n: item.duration_hours })}
                  </span>
                </div>
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
                reason: item.recommendation_reason || t("resource.reasonFallback"),
              })}
            </p>
            <p>
              {t("resource.matchLevel", {
                level: t(`resource.matchLevel.${resourceMatchLevel(item)}`),
              })}
            </p>
            <a href={item.url} target="_blank" rel="noreferrer">
              {t("resource.open")}
            </a>
            <div className="tags">
              {item.skills.map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
            </div>
            <div className="resource-project-grid">
              <section className="resource-detail-card resource-detail-project">
                <span className="resource-detail-label">{t("resource.projectOverview")}</span>
                <h3>{item.project.title}</h3>
                <p>{item.project.task}</p>
              </section>
              <section className="resource-detail-card">
                <span className="resource-detail-label">{t("resource.deliverable")}</span>
                <ul>
                  {item.project.deliverables.map((value) => (
                    <li key={value}>{value}</li>
                  ))}
                </ul>
              </section>
              <section className="resource-detail-card">
                <span className="resource-detail-label">{t("resource.criteria")}</span>
                <ul>
                  {item.project.completion_criteria.map((value) => (
                    <li key={value}>{value}</li>
                  ))}
                </ul>
              </section>
              <section className="resource-detail-card resource-detail-cv">
                <span className="resource-detail-label">{t("resource.cvOutput")}</span>
                <p>{item.project.cv_bullet_template}</p>
              </section>
            </div>
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
                <p className="reflection-requirement" role="status">
                  {(reflections[item.id] || "").trim().length < 10
                    ? t("resource.reflectionMinimum")
                    : t("resource.reflectionReady")}
                </p>
                <button
                  disabled={draftingId === item.id || drafted[item.id]}
                  onClick={() => void createDraft(item)}
                >
                  {drafted[item.id]
                    ? t("resource.draftCreated")
                    : draftingId === item.id
                      ? t("shared.saving")
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
