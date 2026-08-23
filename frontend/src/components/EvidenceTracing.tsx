import { useState } from "react";
import type { Material } from "../types/material";
import { useT } from "../i18n/LanguageProvider";

/**
 * Evidence tracing panel. Each citation is a confirmed experience used by the
 * generator. We deliberately do not claim a sentence-level mapping because
 * the material schema records evidence sources, not offsets within generated
 * text. This keeps the safety promise precise rather than overstating it.
 */
export function EvidenceTracing({ material }: { material: Material }) {
  const t = useT();
  const [challenged, setChallenged] = useState<number | null>(null);
  const sources = material.sources || [];

  return (
    <section className="card evidence-panel" aria-label={t("evidence.title")}>
      <h2>{t("evidence.title")}</h2>
      <p className="privacy-note">{t("evidence.sub")}</p>
      {sources.length ? (
        <>
          <p className="evidence-count">
            {t("evidence.linked", { n: sources.length })}
          </p>
          <ul className="evidence-list">
            {sources.map((source, index) => (
              <li
                key={`${source.experience_id}-${index}`}
                className="evidence-item"
              >
                <strong>
                  {t("evidence.experience")}：{source.experience_title}
                </strong>
                {source.claim && (
                  <p>
                    <span className="evidence-tag">{t("evidence.claim")}</span>{" "}
                    {source.claim}
                  </p>
                )}
                {source.text && <small>{source.text}</small>}
                <button
                  type="button"
                  className="text-action compact"
                  onClick={() =>
                    setChallenged(challenged === index ? null : index)
                  }
                >
                  {t("challenge.open")}
                </button>
                {challenged === index && (
                  <div className="claim-challenge" role="note">
                    <strong>{t("challenge.title")}</strong>
                    <p>{t("challenge.context")}</p>
                    <p>{t("challenge.limit")}</p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p>{t("evidence.noSources")}</p>
      )}
    </section>
  );
}
