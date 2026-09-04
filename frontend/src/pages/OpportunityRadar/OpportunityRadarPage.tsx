import { useEffect, useState } from "react";
import { useI18n, useT } from "../../i18n/LanguageProvider";
import {
  deleteOpportunitySearch,
  importOpportunityAndTrack,
  listOpportunitySearches,
  searchOpportunities,
} from "../../services/opportunityApi";
import type { OpportunitySearch } from "../../types/opportunity";
import type { Job } from "../../types/job";
import type { TrackedApplication } from "../../types/tracker";
import { listExperiences } from "../../services/profileApi";
import type { Experience } from "../../types/experience";

export function OpportunityRadarPage({
  onJobImported,
  onJobTracked,
  hideHero = false,
}: {
  onJobImported?: (job: Job) => void;
  onJobTracked?: (job: Job, tracker: TrackedApplication) => void;
  hideHero?: boolean;
}) {
  const t = useT();
  const { language } = useI18n();
  const [careerGoal, setCareerGoal] = useState("");
  const [careerCategory, setCareerCategory] = useState("");
  const [location, setLocation] = useState("Hong Kong");
  const [workPreference, setWorkPreference] = useState<
    "any" | "onsite" | "hybrid" | "remote"
  >("any");
  const [timing, setTiming] = useState("");
  const [searchModes, setSearchModes] = useState<Array<"ai" | "official_ats">>([
    "official_ats",
  ]);
  const [consent, setConsent] = useState(false);
  const [searches, setSearches] = useState<OpportunitySearch[]>([]);
  const [evidence, setEvidence] = useState<Experience[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<number[]>([]);
  const [evidenceMode, setEvidenceMode] = useState<"all" | "custom">("all");
  const [evidenceLoading, setEvidenceLoading] = useState(true);
  const [active, setActive] = useState<OpportunitySearch | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState<number | null>(null);
  const [deletingSearch, setDeletingSearch] = useState<number | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void listOpportunitySearches()
      .then((items) => {
        setSearches(items);
        setActive(items[0] || null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    // The backend deliberately sends at most the same 12 confirmed records
    // shown here, so consent is specific and inspectable rather than vague.
    void listExperiences({ confirmed: true, limit: 500 })
      .then((items) => {
        setEvidence(items);
        setSelectedEvidenceIds(items.map((item) => item.id));
      })
      .catch(() => {
        setEvidence([]);
        setSelectedEvidenceIds([]);
      })
      .finally(() => setEvidenceLoading(false));
  }, []);

  const selectedEvidence = evidence.filter((item) =>
    selectedEvidenceIds.includes(item.id),
  );
  const allEvidenceSelected =
    evidence.length > 0 && selectedEvidenceIds.length === evidence.length;

  const useAllEvidence = () => {
    setEvidenceMode("all");
    setSelectedEvidenceIds(evidence.map((item) => item.id));
  };

  const chooseSpecificEvidence = () => {
    setEvidenceMode("custom");
  };

  const toggleEvidence = (id: number, checked: boolean) => {
    setEvidenceMode("custom");
    setSelectedEvidenceIds((current) =>
      checked
        ? [...new Set([...current, id])]
        : current.filter((value) => value !== id),
    );
  };

  const toggleSearchMode = (mode: "ai" | "official_ats", checked: boolean) => {
    setSearchModes((current) =>
      checked
        ? [...new Set([...current, mode])]
        : current.filter((item) => item !== mode),
    );
  };

  const resultMessage = (search: OpportunitySearch) => {
    const modes = search.search_modes?.length
      ? search.search_modes
      : [search.used_fallback ? "official_ats" : "ai"];
    const outcomes = search.strategy_outcomes ?? [];
    const selectedAi = modes.includes("ai");
    const selectedAts = modes.includes("official_ats");
    const ai = outcomes.find((item) => item.mode === "ai");
    const ats = outcomes.find((item) => item.mode === "official_ats");
    if (selectedAi && selectedAts) {
      if (ai?.status === "success" && ats?.status === "success")
        return t("opportunity.bothSuccess");
      if (ats?.status === "success") return t("opportunity.bothOfficialOnly");
      if (ai?.status === "success") return t("opportunity.bothAiOnly");
      return t("opportunity.bothFailed");
    }
    if (selectedAi)
      return ai?.status === "success"
        ? t("opportunity.aiSuccess")
        : t("opportunity.aiFailed");
    return ats?.status === "success"
      ? t("opportunity.officialSuccess")
      : t("opportunity.officialFailed");
  };

  const displayReason = (
    opportunity: OpportunitySearch["opportunities"][number],
  ) => {
    const isLegacyGeneric =
      /official applicant-tracking|官方招聘系统|官方招聘系統/i.test(
        opportunity.why_match,
      );
    if (!isLegacyGeneric) return opportunity.why_match;
    return t("opportunity.officialReason", {
      role: opportunity.title,
      evidence:
        opportunity.evidence_used
          .slice(0, 2)
          .join(language === "en" ? ", " : "、") ||
        t("opportunity.profileOnly"),
    });
  };

  // The backend ranks the requested location above other offices. Keep real,
  // verified alternatives visible when there is no current exact-city match.
  const visibleOpportunities = (search: OpportunitySearch) => {
    return search.opportunities;
  };

  const hasRequestedLocation = (search: OpportunitySearch) => {
    const normalize = (value: string) => {
      const compact = value.trim().toLowerCase();
      return compact === "hkg" || compact === "香港" ? "hong kong" : compact;
    };
    const requested = normalize(search.location);
    if (!requested) return true;
    return search.opportunities.some((item) => {
      const actual = normalize(item.location || "");
      return actual.includes(requested) || requested.includes(actual);
    });
  };

  const discover = async () => {
    if (!consent) {
      setError(t("opportunity.consentRequired"));
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await searchOpportunities({
        career_goal: careerGoal.trim(),
        location: location.trim(),
        work_preference: workPreference,
        timing: timing.trim(),
        language,
        search_modes: searchModes,
        experience_ids: selectedEvidenceIds,
        consent_to_web_search: true,
        limit: 5,
      });
      setSearches((previous) => [
        result,
        ...previous.filter((item) => item.id !== result.id),
      ]);
      setActive(result);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : t("opportunity.failed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const importRole = async (index: number) => {
    if (!active) return;
    setImporting(index);
    setError("");
    try {
      const result = await importOpportunityAndTrack(active.id, index);
      onJobImported?.(result.job);
      onJobTracked?.(result.job, result.tracker);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : t("opportunity.importFailed"),
      );
    } finally {
      setImporting(null);
    }
  };

  const removeSearch = async (search: OpportunitySearch) => {
    if (!window.confirm(t("opportunity.deleteHistoryConfirm"))) return;
    setDeletingSearch(search.id);
    setError("");
    try {
      await deleteOpportunitySearch(search.id);
      setSearches((previous) => {
        const remaining = previous.filter((item) => item.id !== search.id);
        setActive((current) =>
          current?.id === search.id ? remaining[0] || null : current,
        );
        return remaining;
      });
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : t("opportunity.deleteHistoryFailed"),
      );
    } finally {
      setDeletingSearch(null);
    }
  };

  return (
    <main className="product-page opportunity-page">
      {!hideHero && <header className="product-hero opportunity-hero">
        <div>
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span className="radar-wordmark">· OPPORTUNITY RADAR</span>
          </p>
          <h1>{t("opportunity.heroTitle")}</h1>
          <p className="sub">{t("opportunity.heroSub")}</p>
        </div>
        <div className="hero-orb" aria-hidden="true">
          <span>⌁</span>
        </div>
      </header>}

      <section className="product-content opportunity-content">
        <section className="card radar-brief-card">
          <div className="section-heading compact-heading">
            <div>
              <p className="section-kicker">01 · DISCOVERY BRIEF</p>
              <h2>{t("opportunity.briefTitle")}</h2>
              <p>{t("opportunity.briefSub")}</p>
            </div>
          </div>
          <div className="radar-form-grid">
            <fieldset className="radar-search-mode form-field-wide">
              <legend>{t("opportunity.searchMode")}</legend>
              <label
                className={
                  searchModes.includes("official_ats") ? "selected" : ""
                }
              >
                <input
                  type="checkbox"
                  name="search-mode-official"
                  checked={searchModes.includes("official_ats")}
                  onChange={(event) =>
                    toggleSearchMode("official_ats", event.target.checked)
                  }
                />
                <span>
                  <strong>{t("opportunity.officialAtsMode")}</strong>
                  <small>{t("opportunity.officialAtsModeSub")}</small>
                </span>
              </label>
              <label className={searchModes.includes("ai") ? "selected" : ""}>
                <input
                  type="checkbox"
                  name="search-mode-ai"
                  checked={searchModes.includes("ai")}
                  onChange={(event) =>
                    toggleSearchMode("ai", event.target.checked)
                  }
                />
                <span>
                  <strong>{t("opportunity.aiMode")}</strong>
                  <small>{t("opportunity.aiModeSub")}</small>
                </span>
              </label>
            </fieldset>
            <label className="form-field form-field-wide">
              <span>{t("opportunity.goal")}</span>
              <div className="radar-category-control">
                <select
                  aria-label={t("opportunity.category")}
                  value={careerCategory}
                  onChange={(event) => {
                    const value = event.target.value;
                    setCareerCategory(value);
                    setCareerGoal(
                      value && value !== "other"
                        ? t("opportunity.categorySearchPrompt", {
                            category: t(`opportunity.category.${value}`),
                          })
                        : "",
                    );
                  }}
                >
                  <option value="">{t("opportunity.categoryPlaceholder")}</option>
                  {[
                    "accounting", "admin", "banking", "consulting", "creative",
                    "customer", "data", "education", "engineering", "finance",
                    "healthcare", "hr", "legal", "marketing", "operations",
                    "product", "quant", "research", "sales", "software", "other",
                  ].map((category) => (
                    <option key={category} value={category}>
                      {t(`opportunity.category.${category}`)}
                    </option>
                  ))}
                </select>
                <small>{t("opportunity.categoryHelp")}</small>
              </div>
              {careerCategory === "other" && (
                <textarea
                  aria-label={t("opportunity.goal")}
                  value={careerGoal}
                  onChange={(event) => setCareerGoal(event.target.value)}
                  maxLength={1200}
                  placeholder={t("opportunity.otherGoalPlaceholder")}
                />
              )}
            </label>
            <label className="form-field">
              <span>{t("opportunity.location")}</span>
              <input
                aria-label={t("opportunity.location")}
                value={location}
                onChange={(event) => setLocation(event.target.value)}
                maxLength={160}
              />
            </label>
            <label className="form-field">
              <span>{t("opportunity.workPreference")}</span>
              <select
                aria-label={t("opportunity.workPreference")}
                value={workPreference}
                onChange={(event) =>
                  setWorkPreference(event.target.value as typeof workPreference)
                }
              >
                <option value="any">{t("opportunity.any")}</option>
                <option value="onsite">{t("opportunity.onsite")}</option>
                <option value="hybrid">{t("opportunity.hybrid")}</option>
                <option value="remote">{t("opportunity.remote")}</option>
              </select>
            </label>
            <label className="form-field">
              <span>{t("opportunity.timing")}</span>
              <input
                aria-label={t("opportunity.timing")}
                value={timing}
                onChange={(event) => setTiming(event.target.value)}
                maxLength={160}
                placeholder={t("opportunity.timingPlaceholder")}
              />
            </label>
          </div>
          <section
            className="radar-evidence-preview"
            aria-label={t("opportunity.evidencePreviewTitle")}
          >
            <div className="radar-evidence-preview-heading">
              <div>
                <p className="section-kicker">CONFIRMED EVIDENCE PREVIEW</p>
                <h3>{t("opportunity.evidencePreviewTitle")}</h3>
                <p>{t("opportunity.evidencePreviewSub")}</p>
              </div>
              <span className="radar-evidence-count">
                {evidenceLoading
                  ? "…"
                  : t("opportunity.evidenceSelectedCount", {
                      selected: selectedEvidence.length,
                      total: evidence.length,
                    })}
              </span>
            </div>
            {!evidenceLoading && evidence.length > 0 && (
              <div
                className="radar-evidence-controls"
                role="group"
                aria-label={t("opportunity.evidenceMode")}
              >
                <button
                  type="button"
                  className={evidenceMode === "all" ? "active" : ""}
                  onClick={useAllEvidence}
                >
                  {t("opportunity.useAllEvidence", { n: evidence.length })}
                </button>
                <button
                  type="button"
                  className={evidenceMode === "custom" ? "active" : ""}
                  onClick={chooseSpecificEvidence}
                >
                  {t("opportunity.chooseEvidence")}
                </button>
                {evidenceMode === "custom" && (
                  <label className="radar-evidence-select-all">
                    <input
                      type="checkbox"
                      checked={allEvidenceSelected}
                      onChange={(event) =>
                        event.target.checked
                          ? useAllEvidence()
                          : setSelectedEvidenceIds([])
                      }
                    />
                    {t("opportunity.selectAllEvidence")}
                  </label>
                )}
              </div>
            )}
            {!evidenceLoading && evidence.length === 0 ? (
              <p className="radar-evidence-empty">
                {t("opportunity.noEvidence")}
              </p>
            ) : (
              <div className="radar-evidence-list">
                {evidence.map((item) => (
                  <article
                    className={`radar-evidence-item ${selectedEvidenceIds.includes(item.id) ? "selected" : ""}`}
                    key={item.id}
                  >
                    {evidenceMode === "custom" && (
                      <label className="radar-evidence-check">
                        <input
                          type="checkbox"
                          checked={selectedEvidenceIds.includes(item.id)}
                          onChange={(event) =>
                            toggleEvidence(item.id, event.target.checked)
                          }
                        />
                        {t("opportunity.useThisEvidence")}
                      </label>
                    )}
                    <p className="experience-field-label">
                      {t(`profile.category.${item.category}`)}
                    </p>
                    <strong>{item.title}</strong>
                    {item.organization && (
                      <small>
                        {t("profile.display.organization")}: {item.organization}
                      </small>
                    )}
                    {item.description && (
                      <p>
                        {item.description.length > 180
                          ? `${item.description.slice(0, 177)}…`
                          : item.description}
                      </p>
                    )}
                    {item.skills.length > 0 && (
                      <div className="tags">
                        {item.skills.slice(0, 6).map((skill) => (
                          <span key={skill}>{skill}</span>
                        ))}
                      </div>
                    )}
                  </article>
                ))}
              </div>
            )}
          </section>
          <label className="radar-consent">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
            />
            <span>
              <strong>{t("opportunity.consent")}</strong>
              <small>{t("opportunity.consentSub")}</small>
            </span>
          </label>
          <div className="radar-actions">
            <p>{t("opportunity.safetyNote")}</p>
            <button
              disabled={
                busy ||
                !consent ||
                selectedEvidence.length === 0 ||
                searchModes.length === 0
              }
              onClick={() => void discover()}
            >
              {busy ? t("opportunity.searching") : t("opportunity.search")}
            </button>
          </div>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </section>

        {searches.length > 0 && (
          <section
            className="radar-history"
            aria-label={t("opportunity.history")}
          >
            <span>{t("opportunity.history")}</span>
            {searches.slice(0, 8).map((search) => (
              <div
                className={`radar-history-item ${active?.id === search.id ? "active" : ""}`}
                key={search.id}
              >
                <button
                  className="radar-history-select"
                  onClick={() => setActive(search)}
                >
                  {search.career_goal || t("opportunity.profileOnly")}
                </button>
                <button
                  className="radar-history-delete"
                  aria-label={t("opportunity.deleteHistory")}
                  title={t("opportunity.deleteHistory")}
                  disabled={deletingSearch === search.id}
                  onClick={() => void removeSearch(search)}
                >
                  ×
                </button>
              </div>
            ))}
          </section>
        )}

        {active &&
          (() => {
            const opportunities = visibleOpportunities(active);
            return (
              <section className="radar-results">
                <div className="section-heading compact-heading">
                  <div>
                    <p className="section-kicker">
                      02 · EVIDENCE-FIRST RESULTS
                    </p>
                    <h2>{t("opportunity.resultsTitle")}</h2>
                    <p>{resultMessage(active)}</p>
                    {opportunities.length > 0 && !hasRequestedLocation(active) && (
                      <p className="opportunity-location-note">
                        {t("opportunity.locationAlternative", {
                          location: active.location,
                        })}
                      </p>
                    )}
                  </div>
                </div>
                {opportunities.length === 0 ? (
                  <div className="card radar-empty">
                    <h3>
                      {active.unavailable_reason === "quota_exhausted"
                        ? t("opportunity.quotaTitle")
                        : t("opportunity.noResultsTitle")}
                    </h3>
                    <p>
                      {active.unavailable_reason === "quota_exhausted"
                        ? t("opportunity.quotaSub")
                        : t("opportunity.noResultsSub")}
                    </p>
                  </div>
                ) : (
                  opportunities.map((opportunity) => {
                    const originalIndex =
                      active.opportunities.indexOf(opportunity);
                    return (
                      <article
                        className="card opportunity-card"
                        key={`${active.id}-${opportunity.company}-${opportunity.title}`}
                      >
                        <header>
                          <div>
                            <p className="section-kicker">
                              {opportunity.company}
                            </p>
                            <h3>{opportunity.title}</h3>
                            <p className="opportunity-meta">
                              {[
                                opportunity.location,
                                opportunity.employment_type,
                              ]
                                .filter(Boolean)
                                .join(" · ") ||
                                t("opportunity.detailsOnSource")}
                            </p>
                          </div>
                          <a
                            href={opportunity.source_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            {t("opportunity.openSource")} ↗
                          </a>
                        </header>
                        <div className="opportunity-reason">
                          <strong>{t("opportunity.whyMatch")}</strong>
                          <p>{displayReason(opportunity)}</p>
                        </div>
                        <div className="opportunity-evidence-grid">
                          <div>
                            <strong>{t("opportunity.evidence")}</strong>
                            <ul>
                              {opportunity.evidence_used.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div>
                            <strong>{t("opportunity.gaps")}</strong>
                            <ul>
                              {(opportunity.gaps_to_address.length
                                ? opportunity.gaps_to_address
                                : [t("opportunity.gapsNeedReview")]
                              ).map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                        {opportunity.next_step && (
                          <p className="opportunity-next">
                            <strong>{t("opportunity.nextStep")}</strong>
                            {opportunity.next_step}
                          </p>
                        )}
                        <footer>
                          <small>
                            {t(
                              opportunity.source_search_mode === "ai"
                                ? "opportunity.sourceVerifiedAi"
                                : "opportunity.sourceVerifiedOfficial",
                              { source: opportunity.source_title },
                            )}
                          </small>
                          <button
                            disabled={importing !== null}
                            onClick={() => void importRole(originalIndex)}
                          >
                            {importing === originalIndex
                              ? t("opportunity.importing")
                              : t("opportunity.importAndTrack")}
                          </button>
                        </footer>
                      </article>
                    );
                  })
                )}
              </section>
            );
          })()}
      </section>
    </main>
  );
}
