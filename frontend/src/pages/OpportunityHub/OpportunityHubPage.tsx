import { useEffect, useMemo, useState } from "react";
import type { NavigationJob } from "../../types/dashboard";
import type { Job } from "../../types/job";
import type { TrackedApplication } from "../../types/tracker";
import { useT } from "../../i18n/LanguageProvider";
import { JobAnalysisPage } from "../JobAnalysis/JobAnalysisPage";
import { OpportunityRadarPage } from "../OpportunityRadar/OpportunityRadarPage";
import { listJobs } from "../../services/jobApi";
import { ROLE_FOLDER_ART } from "../../components/roleFolderAssets";
import {
  classifyRole,
  OPPORTUNITY_FOLDER_KEYS,
} from "../../utils/roleClassification";

type OpportunityMode = "discover" | "analyze";
const OPPORTUNITY_HUB_MODE_KEY = "applyease.opportunity-hub-mode";
function getRememberedMode(fallback: OpportunityMode): OpportunityMode {
  try {
    const saved = window.sessionStorage.getItem(OPPORTUNITY_HUB_MODE_KEY);
    return saved === "discover" || saved === "analyze" ? saved : fallback;
  } catch {
    return fallback;
  }
}

export function OpportunityHubPage({
  initialMode = "discover",
  initialJob,
  onJobAnalyzed,
  onReturnToDashboard,
  onOpenResourcePlan,
  onJobTracked,
}: {
  initialMode?: OpportunityMode;
  initialJob?: NavigationJob;
  onJobAnalyzed?: (job: NavigationJob) => void;
  onReturnToDashboard?: () => void;
  onOpenResourcePlan?: (job: NavigationJob) => void;
  onJobTracked?: (job: Job, tracker: TrackedApplication) => void;
}) {
  const t = useT();
  const [mode, setMode] = useState<OpportunityMode>(() =>
    initialJob ? "analyze" : getRememberedMode(initialMode),
  );
  const [savedJobs, setSavedJobs] = useState<Job[]>([]);
  const [selectedLibraryJob, setSelectedLibraryJob] = useState<Job | undefined>();
  const [selectedLibraryFolder, setSelectedLibraryFolder] = useState<string | null>(null);

  const refreshSavedJobs = () => {
    void listJobs().then(setSavedJobs).catch(() => setSavedJobs([]));
  };

  useEffect(() => {
    refreshSavedJobs();
  }, []);

  const groupedJobs = useMemo(() => {
    const groups = new Map<string, Job[]>();
    savedJobs.filter((job) => job.library_saved === true).forEach((job) => {
      const key = classifyRole(job.title, job.company);
      groups.set(key, [...(groups.get(key) || []), job]);
    });
    return groups;
  }, [savedJobs]);

  useEffect(() => {
    try {
      window.sessionStorage.setItem(OPPORTUNITY_HUB_MODE_KEY, mode);
    } catch {
      // Mode persistence is a convenience only.
    }
  }, [mode]);

  return (
    <div className="opportunity-hub-page">
      <header className="product-hero opportunity-hub-hero">
        <div>
          <p className="eyebrow"><strong>APPLYEASE</strong><span className="page-wordmark">· OPPORTUNITY HUB</span></p>
          <h1>{t("hub.heroTitle")}</h1>
        </div>
        <div className="hero-orb hero-orb-job" aria-hidden="true"><span>⌁</span></div>
      </header>
      <section className="opportunity-role-folders opportunity-hub-role-library" aria-label={t("opportunity.foldersTitle")}>
          <div className="section-heading compact-heading">
            <div>
              <p className="section-kicker">ROLE LIBRARY · 01</p>
              <h2>{t("opportunity.foldersTitle")}</h2>
              <p>{t("opportunity.foldersSub")}</p>
            </div>
          </div>
          {savedJobs.filter((job) => job.library_saved === true).length === 0 && (
            <p className="opportunity-folder-empty">{t("opportunity.folderEmpty")}</p>
          )}
          <div className="opportunity-folder-grid">
              {OPPORTUNITY_FOLDER_KEYS.map((folder) => {
                const jobs = groupedJobs.get(folder) || [];
                return (
                    <button type="button" key={folder} className={`opportunity-folder-card ${jobs.length ? "" : "empty"} ${selectedLibraryFolder === folder ? "selected" : ""}`} disabled={!jobs.length} title={jobs.length ? jobs.map((job) => `${job.title} · ${job.company}`).join("\n") : undefined} onClick={() => setSelectedLibraryFolder((current) => current === folder ? null : folder)}>
                    <img className="opportunity-folder-cover" src={ROLE_FOLDER_ART[folder]} alt="" aria-hidden="true" />
                    <span><strong>{t(`opportunity.folder.${folder}`)}</strong><small>{t("opportunity.folderCount", { n: jobs.length })}</small></span>
                    <span className="opportunity-folder-arrow" aria-hidden="true">→</span>
                  </button>
                );
              })}
          </div>
          {selectedLibraryFolder && (groupedJobs.get(selectedLibraryFolder) || []).length > 0 && (
            <div className="opportunity-library-role-list" aria-label={t("opportunity.folderSelectRole")}>
              {(groupedJobs.get(selectedLibraryFolder) || []).map((job) => (
                <button key={job.id} type="button" onClick={() => { setSelectedLibraryJob(job); setMode("analyze"); }}>
                  <strong>{job.title}</strong>
                  <span>{job.company}</span>
                </button>
              ))}
            </div>
          )}
      </section>
      <section className="product-content opportunity-hub-choice" aria-label={t("hub.choiceLabel")}>
        <button
          type="button"
          className={`opportunity-path-card discover ${mode === "discover" ? "active" : ""}`}
          aria-pressed={mode === "discover"}
          onClick={() => setMode("discover")}
        >
          <span className="opportunity-path-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><circle cx="11" cy="11" r="6.5" /><path d="m16 16 4.2 4.2M5 11h12M11 5v12" /></svg>
          </span>
          <span className="opportunity-path-copy">
            <small>01 · DISCOVER</small>
            <strong>{t("hub.discoverTitle")}</strong>
            <span>{t("hub.discoverSub")}</span>
          </span>
          <span className="opportunity-path-arrow" aria-hidden="true">→</span>
          {mode === "discover" && <em>{t("hub.active")}</em>}
        </button>
        <button
          type="button"
          className={`opportunity-path-card analyze ${mode === "analyze" ? "active" : ""}`}
          aria-pressed={mode === "analyze"}
          onClick={() => setMode("analyze")}
        >
          <span className="opportunity-path-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none"><path d="M5 3.5h10l4 4V20.5H5z" /><path d="M15 3.5v4h4M8.5 12h7M8.5 16h4" /><path d="m15.5 15.5 1.2 1.2 2.8-3.1" /></svg>
          </span>
          <span className="opportunity-path-copy">
            <small>02 · ANALYSE</small>
            <strong>{t("hub.analyzeTitle")}</strong>
            <span>{t("hub.analyzeSub")}</span>
          </span>
          <span className="opportunity-path-arrow" aria-hidden="true">→</span>
          {mode === "analyze" && <em>{t("hub.active")}</em>}
        </button>
      </section>
      {mode === "discover" ? (
        <OpportunityRadarPage hideHero hideRoleLibrary onJobTracked={onJobTracked} />
      ) : (
        <JobAnalysisPage
          hideHero
          initialJob={selectedLibraryJob || initialJob}
          onJobAnalyzed={(job) => {
            refreshSavedJobs();
            onJobAnalyzed?.(job);
          }}
          onReturnToDashboard={onReturnToDashboard}
          onOpenResourcePlan={onOpenResourcePlan}
        />
      )}
    </div>
  );
}
