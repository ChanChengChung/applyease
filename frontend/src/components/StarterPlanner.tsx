import { useState } from "react";
import { useI18n, useT } from "../i18n/LanguageProvider";
import { getStarterPlan } from "../services/resourceApi";
import type { StarterPlan } from "../types/resource";
import { downloadStarterPlan } from "../utils/starterPlanExport";

type Props = {
  mode: "new" | "experienced";
  onImportCV?: () => void;
  onChangeMode?: () => void;
  onOpenLearningPlan?: () => void;
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
}: Props) {
  const t = useT();
  const { language } = useI18n();
  const [interest, setInterest] = useState("");
  const [plan, setPlan] = useState<StarterPlan | null>(null);
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

  const createPlan = async () => {
    if (interest.trim().length < 8) {
      setError(t("starter.minInterest"));
      return;
    }
    try {
      setBusy(true);
      setError("");
      setPlan(
        await getStarterPlan({
          interest: interest.trim(),
          weekly_hours: Math.max(1, Number(weeklyHours) || 1),
          weeks: Math.max(1, Number(weeks) || 1),
          experience_level: level,
          goal,
          preferred_formats: formats,
          experience_level_other: levelOther.trim(),
          goal_other: goalOther.trim(),
          preferred_format_other: formatOther.trim(),
          language,
        }),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("starter.failed"));
    } finally {
      setBusy(false);
    }
  };

  const hasExperience = mode === "experienced";

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
        <span>
          {t("starter.hours", {
            n:
              Math.max(1, Number(weeklyHours) || 0) *
              Math.max(1, Number(weeks) || 0),
          })}
        </span>
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
          <h3>{plan.headline}</h3>
          <p>
            <strong>{t("starter.firstAction")}</strong> {plan.first_action}
          </p>
          <ol>
            {plan.milestones.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
          <div className="starter-resources">
            {plan.resources.map((item) => (
              <a href={item.url} target="_blank" rel="noreferrer" key={item.id}>
                <span>{item.provider}</span>
                <strong>{item.title}</strong>
                <small>{item.description}</small>
              </a>
            ))}
          </div>
          <p className="privacy-note">{t("starter.evidenceNote")}</p>
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
