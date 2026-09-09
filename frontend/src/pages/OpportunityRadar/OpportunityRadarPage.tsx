import { useEffect, useRef, useState } from "react";
import { useI18n, useT } from "../../i18n/LanguageProvider";
import {
  deleteOpportunitySearch,
  importOpportunity,
  importOpportunityAndTrack,
  listOpportunitySearches,
  searchOpportunities,
} from "../../services/opportunityApi";
import type { OpportunityMatch, OpportunitySearch } from "../../types/opportunity";
import type { Job } from "../../types/job";
import type { TrackedApplication } from "../../types/tracker";
import { listExperiences } from "../../services/profileApi";
import { listJobs } from "../../services/jobApi";
import type { Experience } from "../../types/experience";
import { ROLE_FOLDER_ART } from "../../components/roleFolderAssets";
import {
  classifyRole,
  OPPORTUNITY_FOLDER_KEYS,
  type OpportunityFolderKey,
} from "../../utils/roleClassification";

export function OpportunityRadarPage({
  onJobImported,
  onJobTracked,
  hideHero = false,
  hideRoleLibrary = false,
}: {
  onJobImported?: (job: Job) => void;
  onJobTracked?: (job: Job, tracker: TrackedApplication) => void;
  hideHero?: boolean;
  hideRoleLibrary?: boolean;
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
    "ai",
  ]);
  const [consent, setConsent] = useState(false);
  const [searches, setSearches] = useState<OpportunitySearch[]>([]);
  const [evidence, setEvidence] = useState<Experience[]>([]);
  const [selectedEvidenceIds, setSelectedEvidenceIds] = useState<number[]>([]);
  const [evidenceMode, setEvidenceMode] = useState<"all" | "custom">("all");
  const [evidenceLoading, setEvidenceLoading] = useState(true);
  const [active, setActive] = useState<OpportunitySearch | null>(null);
  const [selectedFolder, setSelectedFolder] = useState<OpportunityFolderKey | null>(null);
  const [selectedOpportunityKey, setSelectedOpportunityKey] = useState<string | null>(null);
  const roleFileRef = useRef<HTMLElement | null>(null);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState<string | null>(null);
  const [deletingSearch, setDeletingSearch] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [importErrors, setImportErrors] = useState<Record<string, string>>({});
  const [libraryJobs, setLibraryJobs] = useState<Job[] | null>(null);

  useEffect(() => {
    void listOpportunitySearches()
      .then((items) => {
        setSearches(items);
        setActive(items[0] || null);
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    // The role library is an explicit promotion boundary. Search history is
    // intentionally not enough to make a role appear here. The API migration
    // adds library_saved to every JobRead response, including an empty list,
    // so an empty response must remain an empty library (never a legacy
    // fallback that could leak unreviewed search results into folders).
    void listJobs()
      .then((items) => setLibraryJobs(items.filter((job) => job.library_saved === true)))
      .catch(() => setLibraryJobs([]));
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

  // The backend keeps the requested city as a hard result boundary whenever
  // an exact match exists; this simply renders the saved result set as-is.
  const visibleOpportunities = (search: OpportunitySearch) => {
    return search.opportunities;
  };

  // Search history can contain the same role more than once (for example, a
  // repeated search or a role returned by both providers).  The role library
  // is a library of roles, not a history of result rows, so de-duplicate by a
  // composite source/title/company/location identity.  Including the title
  // prevents two legitimate roles sharing a listing page from being merged.
  const opportunityEntries = (() => {
    const unique = new Map<string, {
      key: string;
      identity: string;
      search: OpportunitySearch;
      opportunity: OpportunityMatch;
      index: number;
      folder: OpportunityFolderKey;
    }>();
    searches.forEach((search) => {
      search.opportunities.forEach((opportunity, index) => {
        const identity = [
          opportunity.source_url,
          opportunity.company,
          opportunity.title,
          opportunity.location,
          opportunity.employment_type,
        ].map((value) => value.trim().toLowerCase()).join("|");
        if (!unique.has(identity)) {
          unique.set(identity, {
            key: `${search.id}:${index}`,
            identity,
            search,
            opportunity,
            index,
            folder: opportunity.folder as OpportunityFolderKey || classifyRole(
              opportunity.title,
              opportunity.company,
              opportunity.employment_type,
              opportunity.location,
            ),
          });
        }
      });
    });
    const entries = Array.from(unique.values());
    if (libraryJobs === null) return entries;
    const promoted = new Set(libraryJobs.map((job) => `${job.company.trim().toLowerCase()}|${job.title.trim().toLowerCase()}`));
    return entries.filter((entry) => promoted.has(`${entry.opportunity.company.trim().toLowerCase()}|${entry.opportunity.title.trim().toLowerCase()}`));
  })();
  const folderEntries = selectedFolder
    ? opportunityEntries.filter((entry) => entry.folder === selectedFolder)
    : [];
  const selectedEntry = folderEntries.find((entry) => entry.key === selectedOpportunityKey) || folderEntries[0] || null;
  const getMatchLabel = (entry: (typeof opportunityEntries)[number]) => {
    const evidenceCount = entry.opportunity.evidence_used.length;
    const gapCount = entry.opportunity.gaps_to_address.length;
    if (evidenceCount >= 3 && gapCount === 0) return t("opportunity.matchVeryHigh");
    if (evidenceCount >= 2 && gapCount <= 1) return t("opportunity.matchHigh");
    if (evidenceCount > 0) return t("opportunity.matchMedium");
    return t("opportunity.matchLow");
  };

  const selectFolder = (folder: OpportunityFolderKey) => {
    const entries = opportunityEntries.filter((entry) => entry.folder === folder);
    setSelectedFolder(folder);
    setSelectedOpportunityKey(entries[0]?.key || null);
    if (entries[0]) setActive(entries[0].search);
  };

  useEffect(() => {
    const element = roleFileRef.current;
    if (!selectedFolder || !selectedEntry || !element) return;
    // The detail file is intentionally below the folder grid. Move focus to
    // it after a folder is selected, so the student sees the analysis rather
    // than only the selected folder state.
    if (typeof element.scrollIntoView === "function") {
      element.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [selectedFolder, selectedEntry?.key]);

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
        career_category: careerCategory,
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
      setSelectedFolder(null);
      setSelectedOpportunityKey(null);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : t("opportunity.failed"),
      );
    } finally {
      setBusy(false);
    }
  };

  const importRole = async (search: OpportunitySearch, index: number, key: string) => {
    setImporting(key);
    setError("");
    setImportErrors((current) => ({ ...current, [key]: "" }));
    try {
      const result = await importOpportunityAndTrack(search.id, index);
      onJobImported?.(result.job);
      onJobTracked?.(result.job, result.tracker);
    } catch (reason) {
      setImportErrors((current) => ({
        ...current,
        [key]: reason instanceof Error ? reason.message : t("opportunity.importFailed"),
      }));
    } finally {
      setImporting(null);
    }
  };

  const importRoleOnly = async (search: OpportunitySearch, index: number, key: string) => {
    setImporting(key);
    setError("");
    setImportErrors((current) => ({ ...current, [key]: "" }));
    try {
      const job = await importOpportunity(search.id, index);
      onJobImported?.(job);
    } catch (reason) {
      setImportErrors((current) => ({
        ...current,
        [key]: reason instanceof Error ? reason.message : t("opportunity.importFailed"),
      }));
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
        if (active?.id === search.id) {
          setSelectedFolder(null);
          setSelectedOpportunityKey(null);
        }
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

  const historySummary = (search: OpportunitySearch) => {
    const goal = search.career_goal.trim();
    // Older records used the generic profile-only label as their saved goal.
    // Do not expose that implementation detail when a result can tell us
    // what the student actually searched for.
    const genericGoals = new Set([
      "证据驱动搜索",
      "證據驅動搜尋",
      "Evidence-led search",
      "Evidence-driven search",
    ]);
    const roleLabels = Array.from(
      new Set(
        search.opportunities
          .map((item) => `${item.company.trim()} · ${item.title.trim()}`)
          .filter((item) => item !== "·"),
      ),
    );
    const label = goal && !genericGoals.has(goal)
      ? goal
      : roleLabels[0] || search.location.trim() || t("opportunity.historyUntitled");
    const extraRoles = roleLabels.length > 1 ? ` +${roleLabels.length - 1}` : "";
    const resultCount = t("opportunity.historyResultCount", {
      n: search.opportunities.length,
    });
    const date = new Date(search.created_at);
    const dateLabel = Number.isNaN(date.getTime())
      ? ""
      : new Intl.DateTimeFormat(language, {
          year: "numeric",
          month: "numeric",
          day: "numeric",
        }).format(date);
    return {
      label: `${label}${extraRoles}`,
      meta: [resultCount, dateLabel].filter(Boolean).join(" · "),
    };
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
                            category: t(`opportunity.folder.${value}`),
                          })
                        : "",
                    );
                  }}
                >
                  <option value="">{t("opportunity.categoryPlaceholder")}</option>
                  {OPPORTUNITY_FOLDER_KEYS.map((category) => (
                    <option key={category} value={category}>
                      {t(`opportunity.folder.${category}`)}
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
            <div className="radar-history-heading">
              <strong>{t("opportunity.history")}</strong>
              <small>{t("opportunity.historySub")}</small>
            </div>
            {searches.slice(0, 8).map((search) => {
              const summary = historySummary(search);
              return (
                <div
                  className={`radar-history-item ${active?.id === search.id ? "active" : ""}`}
                  key={search.id}
                >
                  <button
                    className="radar-history-select"
                    onClick={() => {
                      setActive(search);
                      setSelectedFolder(null);
                      setSelectedOpportunityKey(null);
                    }}
                    title={t("opportunity.historyOpen", { label: summary.label })}
                  >
                    <span className="radar-history-label">{summary.label}</span>
                    <small className="radar-history-meta">{summary.meta}</small>
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
              );
            })}
            </section>
        )}

        {!hideRoleLibrary && <section className="opportunity-role-folders" aria-label={t("opportunity.foldersTitle")}>
          <div className="section-heading compact-heading">
            <div>
              <p className="section-kicker">ROLE LIBRARY · 01</p>
              <h2>{t("opportunity.foldersTitle")}</h2>
              <p>{t("opportunity.foldersSub")}</p>
            </div>
          </div>
          {opportunityEntries.length === 0 && (
            <p className="opportunity-folder-empty">{t("opportunity.folderEmpty")}</p>
          )}
          <div className="opportunity-folder-grid">
              {OPPORTUNITY_FOLDER_KEYS.map((folder) => {
                const folderItems = opportunityEntries.filter((entry) => entry.folder === folder);
                const count = folderItems.length;
                const selected = selectedFolder === folder;
                return (
                  <button
                    key={folder}
                    type="button"
                    className={`opportunity-folder-card ${selected ? "selected" : ""} ${count === 0 ? "empty" : ""}`}
                    aria-pressed={selected}
                    disabled={count === 0}
                    title={count ? folderItems.map((entry) => `${entry.opportunity.title} · ${entry.opportunity.company}`).join("\n") : undefined}
                    onClick={() => selectFolder(folder)}
                  >
                    <img className="opportunity-folder-cover" src={ROLE_FOLDER_ART[folder]} alt="" aria-hidden="true" />
                    <span>
                      <strong>{t(`opportunity.folder.${folder}`)}</strong>
                      <small>{t("opportunity.folderCount", { n: count })}</small>
                    </span>
                    <span className="opportunity-folder-arrow" aria-hidden="true">→</span>
                  </button>
                );
              })}
          </div>
        </section>}

        {selectedFolder && selectedEntry && (
          <section ref={roleFileRef} className="opportunity-role-file" aria-label={t("opportunity.folderDetailTitle")}>
            <div className="opportunity-role-file-header">
              <div>
                <p className="section-kicker">{t("opportunity.folderDetailKicker")}</p>
                <p className="opportunity-role-file-label">{t("opportunity.folderDetailTitle")}</p>
                <h2>{t(`opportunity.folder.${selectedFolder}`)}</h2>
                <p>{t("opportunity.folderCount", { n: folderEntries.length })}</p>
              </div>
            </div>
            <div className="opportunity-role-picker" role="listbox" aria-label={t("opportunity.folderSelectRole")}>
              {folderEntries.map((entry) => (
                <button
                  key={entry.key}
                  type="button"
                  role="option"
                  aria-selected={selectedEntry.key === entry.key}
                  className={selectedEntry.key === entry.key ? "selected" : ""}
                  onClick={() => {
                    setSelectedOpportunityKey(entry.key);
                    setActive(entry.search);
                  }}
                >
                  <strong>{entry.opportunity.company} · {entry.opportunity.title}</strong>
                  <small>{entry.opportunity.location || t("opportunity.detailsOnSource")}</small>
                </button>
              ))}
            </div>
            <div className="opportunity-role-files-grid">
              {folderEntries.map((entry) => (
                <article className="opportunity-role-file-card" key={entry.key}>
                  <header className="opportunity-role-file-card-header">
                    <div>
                      <p className="section-kicker">ROLE ANALYSIS · EVIDENCE-FIRST</p>
                      <h3>{entry.opportunity.title}</h3>
                      <p>{entry.opportunity.company}{entry.opportunity.location ? ` · ${entry.opportunity.location}` : ""}</p>
                    </div>
                    <a href={entry.opportunity.source_url} target="_blank" rel="noreferrer">
                      {t("opportunity.openSource")} ↗
                    </a>
                  </header>
                  <div className="opportunity-role-sections">
                    <article className="opportunity-role-section eligibility">
                      <p className="section-kicker">APPLY BEFORE YOU DECIDE</p>
                      <h3>{t("opportunity.eligibilitySection")}</h3>
                      <p>{entry.opportunity.gaps_to_address.length ? t("opportunity.gapsNeedReview") : t("opportunity.readyToReview")}</p>
                      <span className="opportunity-status-pill">{getMatchLabel(entry)}</span>
                    </article>
                    <article className="opportunity-role-section">
                      <p className="section-kicker">MATCH SIGNAL</p>
                      <h3>{t("opportunity.matchSignal")}</h3>
                      <strong className="opportunity-match-level">{getMatchLabel(entry)}</strong>
                      <p>{entry.opportunity.why_match}</p>
                    </article>
                    <article className="opportunity-role-section full-width">
                      <p className="section-kicker">EVIDENCE MAP</p>
                      <h3>
                        {entry.key === selectedEntry.key
                          ? t("opportunity.evidenceMap")
                          : `${t("opportunity.evidenceMap")} · ${entry.opportunity.title}`}
                      </h3>
                      <div className="opportunity-role-evidence-grid">
                        <div>
                          <strong>
                            {entry.key === selectedEntry.key
                              ? t("opportunity.matchedEvidence")
                              : `${t("opportunity.matchedEvidence")} · ${entry.opportunity.title}`}
                          </strong>
                          {entry.opportunity.evidence_used.length ? (
                            <ul>{entry.opportunity.evidence_used.map((item) => <li key={item}>{item}</li>)}</ul>
                          ) : <p>{t("opportunity.noEvidenceUsed")}</p>}
                        </div>
                        <div>
                          <strong>{t("opportunity.reviewGaps")}</strong>
                          {entry.opportunity.gaps_to_address.length ? (
                            <ul>{entry.opportunity.gaps_to_address.map((item) => <li key={item}>{item}</li>)}</ul>
                          ) : <p>{t("opportunity.noGaps")}</p>}
                        </div>
                      </div>
                      {entry.opportunity.next_step && (
                        <p className="opportunity-role-next"><strong>{t("opportunity.folderNextStep")}：</strong>{entry.opportunity.next_step}</p>
                      )}
                      <div className="opportunity-role-actions">
                        <button type="button" className="secondary" onClick={() => void importRoleOnly(entry.search, entry.index, `${entry.key}:workspace`)} disabled={importing !== null}>
                          {importing === `${entry.key}:workspace` ? t("opportunity.importing") : t("opportunity.importToWorkspace")}
                        </button>
                        <button type="button" onClick={() => void importRole(entry.search, entry.index, `${entry.key}:track`)} disabled={importing !== null}>
                          {importing === `${entry.key}:track` ? t("opportunity.importing") : t("opportunity.importAndTrack")}
                        </button>
                      </div>
                      {(importErrors[`${entry.key}:workspace`] || importErrors[`${entry.key}:track`]) && (
                        <p className="opportunity-role-import-error" role="alert">
                          {importErrors[`${entry.key}:workspace`] || importErrors[`${entry.key}:track`]}
                        </p>
                      )}
                    </article>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}

        {!selectedFolder && active &&
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
                            onClick={() => void importRole(active, originalIndex, `${active.id}:${originalIndex}`)}
                          >
                            {importing === `${active.id}:${originalIndex}`
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
