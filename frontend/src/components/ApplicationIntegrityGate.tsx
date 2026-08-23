import type { Material } from "../types/material";
import { useT } from "../i18n/LanguageProvider";

/**
 * Makes ApplyEase's core product promise visible at the moment a user is about
 * to use generated material: the model may draft, but only confirmed evidence
 * may support an application claim.
 */
export function ApplicationIntegrityGate({ material }: { material: Material }) {
  const t = useT();
  const sourceCount = material.sources?.length || 0;
  const verified = material.fact_check_passed && sourceCount > 0;
  const score = !material.fact_check_passed ? 0 : sourceCount ? 100 : 55;

  return (
    <section
      className={`card integrity-gate ${verified ? "verified" : "review"}`}
    >
      <div>
        <p className="section-kicker">APPLYEASE · INTEGRITY GATE</p>
        <h2>{t("integrity.title")}</h2>
        <p>{t("integrity.sub")}</p>
      </div>
      <div
        className="integrity-score"
        aria-label={t("integrity.score", { score })}
      >
        <strong>{score}</strong>
        <small>/100</small>
      </div>
      <ul>
        <li className={sourceCount ? "pass" : "fail"}>
          {t("integrity.sources", { n: sourceCount })}
        </li>
        <li className={material.fact_check_passed ? "pass" : "fail"}>
          {material.fact_check_passed
            ? t("integrity.factPass")
            : t("integrity.factFail")}
        </li>
        <li>{verified ? t("integrity.ready") : t("integrity.review")}</li>
      </ul>
    </section>
  );
}
