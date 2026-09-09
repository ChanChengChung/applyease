import { useEffect, useState } from "react";
import { useT } from "../i18n/LanguageProvider";
import {
  deleteStarterPlan,
  getSavedStarterPlan,
  getStarterPlan,
  listStarterPlans,
} from "../services/resourceApi";
import type { StarterPlan } from "../types/resource";
import { downloadStarterPlan } from "../utils/starterPlanExport";
import { detectContentLanguage } from "../utils/contentLanguage";

type Props = {
  mode: "new" | "experienced";
  onImportCV?: () => void;
  onChangeMode?: () => void;
  onOpenLearningPlan?: () => void;
  /** Saved plans belong to the learning workspace, not the fresh-start flow. */
  showSavedPlans?: boolean;
};

/**
 * A guided first step for students without a CV. It deliberately stays in the
 * experience bank: a plan becomes a future, user-confirmed piece of evidence,
 * not a claim that the student already has experience.
 */
export function StarterPlanner({
  mode,
  onImportCV,
  onChangeMode,
  onOpenLearningPlan,
  showSavedPlans = true,
}: Props) {
  const t = useT();
  const [interest, setInterest] = useState("");
  const [plan, setPlan] = useState<StarterPlan | null>(null);
  const [savedPlans, setSavedPlans] = useState<StarterPlan[]>([]);
  const [savedPlansLoading, setSavedPlansLoading] = useState(true);
  const [level, setLevel] = useState<"none" | "basic" | "some">("none");
  const [goal, setGoal] = useState<"explore" | "portfolio" | "competition">(
    "explore",
  );
  const [formats, setFormats] = useState<
    Array<"project" | "feedback" | "course">
  >(["project"]);
  const [levelOther, setLevelOther] = useState("");
  const [goalOther, setGoalOther] = useState("");
  const [formatOther, setFormatOther] = useState("");
  const [weeklyHours, setWeeklyHours] = useState("3");
  const [weeks, setWeeks] = useState("4");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const interestTooShort =
    interest.trim().length > 0 && interest.trim().length < 8;

  useEffect(() => {
    if (!showSavedPlans) {
      setSavedPlans([]);
      setSavedPlansLoading(false);
      return;
    }
    let active = true;
    setSavedPlansLoading(true);
    void listStarterPlans()
      .catch(() => getSavedStarterPlan().then((saved) => [saved]))
      .then((plans) => {
        if (!active) return;
        setSavedPlans(plans);
        // Restore the most recently updated plan when this page is reopened.
        if (plans.length) {
          setPlan((current) => current || plans[0]);
          setInterest((current) => current || plans[0].interest);
        }
      })
      .catch(() => {
        // An empty folder is a valid first-run state; it must not block plan creation.
        if (active) setSavedPlans([]);
      })
      .finally(() => {
        if (active) setSavedPlansLoading(false);
      });
    return () => {
      active = false;
    };
  }, [showSavedPlans]);

  const createPlan = async () => {
    if (interest.trim().length < 8) {
      setError(t("starter.minInterest"));
      return;
    }
    try {
      setBusy(true);
      setError("");
      const created = await getStarterPlan({
          interest: interest.trim(),
          weekly_hours: Math.max(1, Number(weeklyHours) || 1),
          weeks: Math.max(1, Number(weeks) || 1),
          experience_level: level,
          goal,
          preferred_formats: formats,
          experience_level_other: levelOther.trim(),
          goal_other: goalOther.trim(),
          preferred_format_other: formatOther.trim(),
          // Plan content follows the student's request, not the interface
          // locale. English intent therefore always produces English output.
          language: detectContentLanguage(interest),
        });
      setPlan(created);
      // POST /starter-plan creates a new durable record. Keep older plans in
      // the folder instead of replacing the local view with only the latest one.
      setSavedPlans((current) => [
        created,
        ...current.filter((saved) => saved.id !== created.id),
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("starter.failed"));
    } finally {
      setBusy(false);
    }
  };

  const openSavedPlan = (saved: StarterPlan) => {
    setPlan(saved);
    setInterest(saved.interest);
    setError("");
  };

  const removeSavedPlan = async (saved: StarterPlan) => {
    if (typeof window !== "undefined" && !window.confirm(t("starter.deleteConfirm"))) {
      return;
    }
    try {
      setBusy(true);
      setError("");
      await deleteStarterPlan(saved.id);
      setSavedPlans((current) => {
        const remaining = current.filter((item) => item.id !== saved.id);
        setPlan((currentPlan) => {
          if (currentPlan?.id !== saved.id) return currentPlan;
          const next = remaining[0] || null;
          if (next) setInterest(next.interest);
          return next;
        });
        return remaining;
      });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("starter.deleteFailed"));
    } finally {
      setBusy(false);
    }
  };

  const hasExperience = mode === "experienced";
  const resultSections = plan
    ? plan.milestone_sections || {
        foundation: plan.milestones.slice(0, 1),
        practice: plan.milestones.slice(1, 2),
        reflection: plan.milestones.slice(2),
      }
    : null;

  return (
    <section className="card starter-planner" aria-labelledby="starter-title">
      <div className="planner-heading">
        <div>
          <p className="section-kicker">00 · START HERE</p>
          <h2 id="starter-title">
            {hasExperience ? t("starter.experienceTitle") : t("starter.title")}
          </h2>
          <p className="privacy-note">
            {hasExperience ? t("starter.experienceSub") : t("starter.sub")}
          </p>
        </div>
        <span className="starter-badge">✦ {t("starter.badge")}</span>
      </div>
      {onChangeMode && (
        <button
          type="button"
          className="starter-change-mode text-action"
          onClick={onChangeMode}
        >
          <span aria-hidden="true">←</span>
          {t("starter.changeMode")}
        </button>
      )}
      {hasExperience && onImportCV && (
        <div className="starter-import-row">
          <span>{t("starter.importHint")}</span>
          <button
            type="button"
            className="secondary-action"
            onClick={onImportCV}
          >
            {t("starter.importCV")}
          </button>
        </div>
      )}
      {showSavedPlans && savedPlans.length > 0 && (
        <section className="starter-plan-folder" aria-label={t("starter.folderTitle")}>
          <div className="starter-plan-folder-heading">
            <div>
              <p className="section-kicker">SAVED PLANS</p>
              <h3>{t("starter.folderTitle")}</h3>
            </div>
            <span>{t("starter.folderCount", { n: savedPlans.length })}</span>
          </div>
          <div className="starter-plan-folder-list">
            {savedPlans.map((saved) => (
              <div
                className={`starter-plan-folder-item ${plan?.id === saved.id ? "selected" : ""}`}
                key={saved.id}
              >
                <button
                  type="button"
                  className="starter-plan-folder-open"
                  onClick={() => openSavedPlan(saved)}
                  aria-pressed={plan?.id === saved.id}
                >
                  <strong>{saved.interest}</strong>
                  <small>{saved.headline}</small>
                </button>
                <button
                  type="button"
                  className="starter-plan-folder-delete"
                  aria-label={`${t("starter.deleteSavedPlan")}: ${saved.interest}`}
                  disabled={busy}
                  onClick={() => void removeSavedPlan(saved)}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
          {savedPlansLoading ? <small className="starter-plan-folder-loading">{t("starter.loadingSavedPlans")}</small> : null}
        </section>
      )}
      <label>
        {t("starter.prompt")}
        <textarea
          value={interest}
          maxLength={1000}
          aria-invalid={interestTooShort}
          aria-describedby={interestTooShort ? "starter-interest-minimum" : undefined}
          onChange={(event) => setInterest(event.target.value)}
          placeholder={t("starter.placeholder")}
        />
      </label>
      {interestTooShort && (
        <p className="starter-interest-minimum" id="starter-interest-minimum" role="status">
          {t("starter.minInterest")}
        </p>
      )}
      <div className="starter-questions">
        <fieldset>
          <legend>{t("starter.level")}</legend>
          {(["none", "basic", "some"] as const).map((value) => (
            <button
              type="button"
              className={level === value ? "active" : ""}
              onClick={() => setLevel(value)}
              key={value}
            >
              {t(`starter.level.${value}`)}
            </button>
          ))}
          <label className="starter-other-field">
            <span>{t("starter.other")}</span>
            <input
              value={levelOther}
              maxLength={300}
              onChange={(event) => setLevelOther(event.target.value)}
              placeholder={t("starter.levelOtherPlaceholder")}
            />
          </label>
        </fieldset>
        <fieldset>
          <legend>{t("starter.goal")}</legend>
          {(["explore", "portfolio", "competition"] as const).map((value) => (
            <button
              type="button"
              className={goal === value ? "active" : ""}
              onClick={() => setGoal(value)}
              key={value}
            >
              {t(`starter.goal.${value}`)}
            </button>
          ))}
          <label className="starter-other-field">
            <span>{t("starter.other")}</span>
            <input
              value={goalOther}
              maxLength={300}
              onChange={(event) => setGoalOther(event.target.value)}
              placeholder={t("starter.goalOtherPlaceholder")}
            />
          </label>
        </fieldset>
        <fieldset>
          <legend>{t("starter.format")}</legend>
          {(["project", "feedback", "course"] as const).map((value) => (
            <label className="inline-check" key={value}>
              <input
                type="checkbox"
                checked={formats.includes(value)}
                onChange={() =>
                  setFormats((current) =>
                    current.includes(value)
                      ? current.filter((item) => item !== value)
                      : [...current, value],
                  )
                }
              />
              {t(`starter.format.${value}`)}
            </label>
          ))}
          <label className="starter-other-field">
            <span>{t("starter.other")}</span>
            <input
              value={formatOther}
              maxLength={300}
              onChange={(event) => setFormatOther(event.target.value)}
              placeholder={t("starter.formatOtherPlaceholder")}
            />
          </label>
        </fieldset>
        <label>
          {t("starter.weeklyHours")}
          <input
            type="number"
            min="1"
            max="30"
            value={weeklyHours}
            onChange={(event) => setWeeklyHours(event.target.value)}
          />
        </label>
        <label>
          {t("starter.weeks")}
          <input
            type="number"
            min="1"
            max="16"
            value={weeks}
            onChange={(event) => setWeeks(event.target.value)}
          />
        </label>
      </div>
      <div className="starter-actions">
        <button
          type="button"
          disabled={busy || interest.trim().length < 8}
          onClick={() => void createPlan()}
        >
          {busy ? t("starter.creating") : t("starter.create")}
        </button>
      </div>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {plan && (
        <div className="starter-result" role="status">
          <p>
            <strong>{t("starter.firstAction")}</strong> {plan.first_action}
          </p>
          <div className="starter-result-phases">
            {(["foundation", "practice", "reflection"] as const).map((key) => (
              <section key={key}>
                <h3>{t(`resource.starterSection.${key}`)}</h3>
                <ol>
                  {(resultSections?.[key] || []).map((item) => <li key={item}>{item}</li>)}
                  {!resultSections?.[key]?.length && <li>{t("starter.noMilestone")}</li>}
                </ol>
              </section>
            ))}
          </div>
          <div className="starter-resources">
            {plan.resources.map((item) => (
              <a href={item.url} target="_blank" rel="noreferrer" key={item.id}>
                <span>{item.provider}</span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </a>
            ))}
          </div>
          <div className="starter-result-actions">
            <button
              type="button"
              className="secondary-action"
              onClick={() => downloadStarterPlan(plan)}
            >
              {t("starter.export")}
            </button>
            {onOpenLearningPlan && (
              <button type="button" onClick={onOpenLearningPlan}>
                {t("starter.openLearningPlan")}
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
