import { useState } from "react";
import type {
  Experience,
  ExperienceCategory,
  ExperienceImpact,
} from "../types/experience";
import { useT } from "../i18n/LanguageProvider";

export function ExperienceCard({
  item,
  onSave,
  onDelete,
  selected = false,
  onSelect,
  impact,
  onExploreOpportunities,
}: {
  item: Experience;
  onSave: (item: Experience) => Promise<void>;
  onDelete: (item: Experience) => Promise<void>;
  selected?: boolean;
  onSelect?: (selected: boolean) => void;
  impact?: ExperienceImpact;
  onExploreOpportunities?: () => void;
}) {
  const [draft, setDraft] = useState(item);
  const [skillsInput, setSkillsInput] = useState(item.skills.join(", "));
  const [editing, setEditing] = useState(false);
  const [moving, setMoving] = useState(false);
  const [folderDraft, setFolderDraft] = useState<ExperienceCategory>(
    item.category,
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const t = useT();
  const achievementSources = [
    ...new Set(
      item.achievements
        .map((achievement) => achievement.source.trim())
        .filter(Boolean),
    ),
  ];

  const reset = () => {
    setDraft(item);
    setSkillsInput(item.skills.join(", "));
    setEditing(false);
    setError("");
  };

  const save = async () => {
    if (!draft.title.trim()) {
      setError(t("shared.titleEmpty"));
      return;
    }
    setSaving(true);
    setError("");
    const skills = [
      ...new Set(
        skillsInput
          .split(/[,，\n]/)
          .map((s) => s.trim())
          .filter(Boolean),
      ),
    ];
    try {
      await onSave({ ...draft, title: draft.title.trim(), skills });
      setEditing(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("shared.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const toggleConfirmation = async () => {
    setSaving(true);
    setError("");
    try {
      await onSave({ ...item, confirmed: !item.confirmed });
    } catch (e) {
      setError(e instanceof Error ? e.message : t("shared.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const moveToFolder = async () => {
    if (folderDraft === item.category) {
      setMoving(false);
      return;
    }
    setSaving(true);
    setError("");
    try {
      await onSave({ ...item, category: folderDraft });
      setMoving(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("shared.saveFailed"));
    } finally {
      setSaving(false);
    }
  };

  const updateAchievement = (index: number, text: string) =>
    setDraft({
      ...draft,
      achievements: draft.achievements.map((a, i) =>
        i === index ? { ...a, text } : a,
      ),
    });

  return (
    <article
      className={`card experience-card ${item.confirmed ? "experience-confirmed" : "experience-pending"}`}
    >
      {editing ? (
        <>
          <div className="form-card-header compact">
            <span className="form-card-icon" aria-hidden="true">
              ✎
            </span>
            <div>
              <p className="section-kicker">EVIDENCE REVIEW</p>
              <h3>{t("shared.edit")}</h3>
              <p>{t("profile.editExperienceSub")}</p>
            </div>
          </div>
          <div className="experience-form-grid experience-editor-grid">
            <label className="form-field">
              {t("profile.field.title")}
              <input
                value={draft.title}
                onChange={(e) => setDraft({ ...draft, title: e.target.value })}
              />
            </label>
            <label className="form-field">
              {t("profile.field.org")}
              <input
                value={draft.organization}
                onChange={(e) =>
                  setDraft({ ...draft, organization: e.target.value })
                }
              />
            </label>
            <label className="form-field">
              {t("profile.field.category")}
              <select
                aria-label={t("profile.field.category")}
                value={draft.category}
                onChange={(e) =>
                  setDraft({
                    ...draft,
                    category: e.target.value as ExperienceCategory,
                  })
                }
              >
                <option value="education">
                  {t("profile.category.education")}
                </option>
                <option value="internship">
                  {t("profile.category.internship")}
                </option>
                <option value="leadership">
                  {t("profile.category.leadership")}
                </option>
                <option value="research">
                  {t("profile.category.research")}
                </option>
                <option value="project">{t("profile.category.project")}</option>
              </select>
            </label>
            <label className="form-field form-field-wide">
              {t("profile.field.desc")}
              <textarea
                value={draft.description}
                onChange={(e) =>
                  setDraft({ ...draft, description: e.target.value })
                }
              />
            </label>
            <label className="form-field">
              {t("profile.field.skills")}
              <input
                value={skillsInput}
                onChange={(e) => setSkillsInput(e.target.value)}
              />
            </label>
          </div>
          <fieldset>
            <legend>{t("shared.achievements")}</legend>
            {draft.achievements.map((a, i) => (
              <label key={`${a.source}-${i}`}>
                {t("shared.achievement", { n: i + 1 })}
                <textarea
                  aria-label={`${t("shared.achievement", { n: i + 1 })}`}
                  value={a.text}
                  onChange={(e) => updateAchievement(i, e.target.value)}
                />
                <small>
                  {t("shared.source", {
                    src: a.source || t("shared.orgEmpty"),
                  })}
                </small>
              </label>
            ))}
          </fieldset>

          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <div className="actions">
            <button onClick={reset} disabled={saving}>
              {t("shared.cancel")}
            </button>
            <button
              onClick={() => void save()}
              disabled={saving || !draft.title.trim()}
            >
              {saving ? t("shared.saving") : t("shared.saveEdit")}
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="card-header">
            <div className="card-title-row">
              {onSelect && (
                <label className="select-experience">
                  <input
                    type="checkbox"
                    aria-label={`${t("shared.select")}：${item.title}`}
                    checked={selected}
                    onChange={(event) => onSelect(event.target.checked)}
                  />
                  {t("shared.select")}
                </label>
              )}
              <div className="experience-heading">
                <p className="experience-field-label">
                  {t("profile.display.name")}
                </p>
                <h3>{item.title}</h3>
                <span
                  className={`experience-category category-${item.category}`}
                >
                  {t(`profile.category.${item.category}`)}
                </span>
                <p className="experience-organization">
                  <span>{t("profile.display.organization")}</span>
                  {item.organization || t("shared.orgEmpty")}
                </p>
                <small className="experience-status">
                  {item.confirmed
                    ? t("profile.evidenceUnlocked")
                    : t("shared.unconfirmed")}
                </small>
              </div>
            </div>
            <div className="actions">
              <button
                onClick={() => {
                  setFolderDraft(item.category);
                  setMoving((value) => !value);
                  setError("");
                }}
                disabled={saving}
              >
                {t("profile.moveFolder")}
              </button>
              <button
                onClick={() => {
                  setDraft(item);
                  setSkillsInput(item.skills.join(", "));
                  setEditing(true);
                }}
                disabled={saving}
              >
                {t("shared.edit")}
              </button>
              <button
                onClick={() => void toggleConfirmation()}
                disabled={saving}
              >
                {saving
                  ? t("shared.saving")
                  : item.confirmed
                    ? t("shared.unconfirm")
                    : t("profile.confirmUnlock")}
              </button>
              <button onClick={() => void onDelete(item)} disabled={saving}>
                {t("shared.delete")}
              </button>
            </div>
          </div>
          {moving && (
            <section
              className="experience-folder-move"
              aria-label={t("profile.moveFolder")}
            >
              <div>
                <p className="experience-field-label">
                  {t("profile.moveFolder")}
                </p>
                <strong>{t("profile.moveFolderSub")}</strong>
              </div>
              <label>
                <span className="sr-only">{t("profile.field.category")}</span>
                <select
                  aria-label={t("profile.field.category")}
                  value={folderDraft}
                  onChange={(event) =>
                    setFolderDraft(event.target.value as ExperienceCategory)
                  }
                >
                  <option value="education">
                    {t("profile.category.education")}
                  </option>
                  <option value="internship">
                    {t("profile.category.internship")}
                  </option>
                  <option value="leadership">
                    {t("profile.category.leadership")}
                  </option>
                  <option value="research">
                    {t("profile.category.research")}
                  </option>
                  <option value="project">
                    {t("profile.category.project")}
                  </option>
                </select>
              </label>
              <div className="experience-folder-move-actions">
                <button
                  type="button"
                  onClick={() => setMoving(false)}
                  disabled={saving}
                >
                  {t("shared.cancel")}
                </button>
                <button
                  type="button"
                  onClick={() => void moveToFolder()}
                  disabled={saving}
                >
                  {saving ? t("shared.saving") : t("profile.moveFolderSave")}
                </button>
              </div>
            </section>
          )}
          <div className="experience-content-block">
            <p className="experience-field-label">
              {t("profile.display.content")}
            </p>
            <p>{item.description || t("profile.display.noContent")}</p>
          </div>
          <div className="experience-skills-block">
            <p className="experience-field-label">
              {t("profile.display.skills")}
            </p>
            <div className="tags">
              {item.skills.map((skill) => (
                <span key={skill}>{skill}</span>
              ))}
              {!item.skills.length && (
                <small>{t("profile.display.noSkills")}</small>
              )}
            </div>
          </div>

          {item.confirmed ? (
            <section
              className="experience-impact"
              aria-label={t("profile.evidenceImpact")}
            >
              <div className="experience-impact-heading">
                <div>
                  <p className="experience-field-label">
                    {t("profile.evidenceImpact")}
                  </p>
                  <strong>{t("profile.evidenceReady")}</strong>
                </div>
                {onExploreOpportunities && (
                  <button
                    className="text-action"
                    onClick={onExploreOpportunities}
                  >
                    {t("profile.useForRadar")} →
                  </button>
                )}
              </div>
              <div className="experience-impact-stats">
                <span>
                  <strong>{impact?.supported_jobs.length || 0}</strong>
                  {t("profile.supportedJobs")}
                </span>
                <span>
                  <strong>{impact?.material_references.length || 0}</strong>
                  {t("profile.materialReferences")}
                </span>
                <span>
                  <strong>
                    {impact?.skills_available.length || item.skills.length}
                  </strong>
                  {t("profile.availableSkills")}
                </span>
              </div>
              {impact?.supported_jobs.length ? (
                <p className="experience-impact-list">
                  {t("profile.supportingRoles")}:{" "}
                  {impact.supported_jobs
                    .map(
                      (job) =>
                        `${job.company || t("shared.orgEmpty")} · ${job.title}`,
                    )
                    .join(" · ")}
                </p>
              ) : (
                <p className="experience-impact-list">
                  {t("profile.noSupportedJobs")}
                </p>
              )}
            </section>
          ) : (
            <aside className="experience-confirmation-note">
              <strong>{t("profile.confirmationTitle")}</strong>
              <p>{t("profile.confirmationSub")}</p>
            </aside>
          )}

          {item.achievements.length > 0 && (
            <div className="experience-achievements-block">
              <div className="experience-achievements-heading">
                <p className="experience-field-label">
                  {t("shared.achievements")}
                </p>
                {achievementSources.length > 0 && (
                  <small>
                    {t("shared.source", {
                      src: achievementSources.join(" · "),
                    })}
                  </small>
                )}
              </div>
              <ul>
                {item.achievements.map((a, i) => (
                  <li key={i}>{a.text}</li>
                ))}
              </ul>
            </div>
          )}

          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </>
      )}
    </article>
  );
}
