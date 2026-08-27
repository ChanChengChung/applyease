import { useState } from "react";
import type { MatchReport } from "../types/job";
import { useT } from "../i18n/LanguageProvider";

function compact(value: string, fallback: string) {
  const clean = value.replace(/\s+/g, " ").trim();
  if (!clean) return fallback;
  const sentence = clean.match(/^.*?[.!?](?:\s|$)/)?.[0] ?? clean;
  return sentence.length > 200 ? `${sentence.slice(0, 197).trim()}…` : sentence;
}

/** Creates rehearsal questions from any saved role's requirements, not generic templates. */
export function QuantInternshipReadinessPack({
  report,
}: {
  report: MatchReport;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const role = `${report.job.company || t("quantPack.thisCompany")} · ${report.job.title}`;
  const responsibility = compact(
    report.job.responsibilities[0] || "",
    t("quantPack.roleFallback"),
  );
  const qualification = compact(
    report.job.qualifications[0] || "",
    t("quantPack.qualificationFallback"),
  );
  const skills =
    report.job.required_skills.slice(0, 3).join(" · ") ||
    t("quantPack.skillFallback");
  const gaps = (report.missing_required_skills ?? report.missing_skills)
    .slice(0, 3)
    .join(" · ");
  const prompts = [
    {
      key: "role",
      label: t("quantPack.promptRoleLabel"),
      question: t("quantPack.promptRole", { role, responsibility }),
      coach: t("quantPack.coachRole"),
    },
    {
      key: "technical",
      label: t("quantPack.promptTechnicalLabel"),
      question: t("quantPack.promptTechnical", { skills }),
      coach: t("quantPack.coachTechnical"),
    },
    {
      key: "judgement",
      label: t("quantPack.promptJudgementLabel"),
      question: t("quantPack.promptJudgement", { qualification }),
      coach: t("quantPack.coachJudgement"),
    },
    {
      key: "gap",
      label: t("quantPack.promptGapLabel"),
      question: gaps
        ? t("quantPack.promptGap", { gaps, role })
        : t("quantPack.promptNoGap", { role }),
      coach: t("quantPack.coachGap"),
    },
  ];

  return (
    <section className="card quant-pack">
      <p className="section-kicker">APPLYEASE · ROLE-SPECIFIC INTERVIEW LAB</p>
      <h2>{t("quantPack.title")}</h2>
      <p className="privacy-note">{t("quantPack.sub", { role })}</p>
      <button
        type="button"
        className="secondary-action"
        onClick={() => setOpen(!open)}
      >
        {open ? t("quantPack.close") : t("quantPack.open")}
      </button>
      {open && (
        <div className="quant-pack-body">
          <p className="quant-pack-notice">{t("quantPack.notice")}</p>
          <div className="quant-role-focus">
            <span>{t("quantPack.roleFocus")}</span>
            <strong>{role}</strong>
          </div>
          <h3>{t("quantPack.rehearse")}</h3>
          <ol className="quant-prompt-list">
            {prompts.map((prompt, index) => (
              <li key={prompt.key} className={done[prompt.key] ? "done" : ""}>
                <label className="quant-prompt-check">
                  <input
                    type="checkbox"
                    checked={Boolean(done[prompt.key])}
                    onChange={(event) =>
                      setDone({ ...done, [prompt.key]: event.target.checked })
                    }
                  />
                  <span>
                    {t("quantPack.questionNumber", { number: index + 1 })}
                  </span>
                </label>
                <div>
                  <small>{prompt.label}</small>
                  <strong>{prompt.question}</strong>
                  <p>
                    <b>{t("quantPack.coach")}</b>
                    {prompt.coach}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      )}
    </section>
  );
}
