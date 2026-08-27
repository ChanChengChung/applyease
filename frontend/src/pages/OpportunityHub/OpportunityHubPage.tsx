import { useEffect, useState } from "react";
import type { NavigationJob } from "../../types/dashboard";
import type { Job } from "../../types/job";
import type { TrackedApplication } from "../../types/tracker";
import { useT } from "../../i18n/LanguageProvider";
import { JobAnalysisPage } from "../JobAnalysis/JobAnalysisPage";
import { OpportunityRadarPage } from "../OpportunityRadar/OpportunityRadarPage";

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
          <p className="sub">{t("hub.heroSub")}</p>
        </div>
        <div className="hero-orb hero-orb-job" aria-hidden="true"><span>⌁</span></div>
      </header>
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
        <OpportunityRadarPage hideHero onJobTracked={onJobTracked} />
      ) : (
        <JobAnalysisPage
          hideHero
          initialJob={initialJob}
          onJobAnalyzed={onJobAnalyzed}
          onReturnToDashboard={onReturnToDashboard}
          onOpenResourcePlan={onOpenResourcePlan}
        />
      )}
    </div>
  );
}
