import { useEffect, useState } from "react";
import { getDashboardSummary } from "../../services/dashboardApi";
import { deleteJob } from "../../services/jobApi";
import type {
  DashboardSummary,
  NavigationJob,
  PageId,
} from "../../types/dashboard";
import { PageFeedback } from "../../components/PageFeedback";
import { useT } from "../../i18n/LanguageProvider";
import { matchLevelTranslationKey, resolveMatchLevel } from "../../utils/matchLevel";

type Props = {
  onNavigate: (target: PageId, job?: NavigationJob) => void;
  onJobLoaded?: (job?: NavigationJob) => void;
  initialJob?: NavigationJob;
};
const metricMarks = ["✦", "⌁", "▣", "↗"];

export function DashboardPage({ onNavigate, onJobLoaded, initialJob }: Props) {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deletingJobId, setDeletingJobId] = useState<number | null>(null);
  const t = useT();
  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getDashboardSummary();
      setSummary(next);
      // A caller may deliberately carry a role (notably the Polymer demo)
      // across pages. Do not replace that explicit selection just because a
      // different record happens to be newest in the database.
      if (next.latest_job && !initialJob) onJobLoaded?.(next.latest_job);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("dashboard.loading"));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, [initialJob]);
  const activeJob = initialJob || summary?.latest_job || undefined;
  const navigate = (target: PageId) => onNavigate(target, activeJob);
  const removeJobWorkspace = async (job: NavigationJob) => {
    if (!window.confirm(t("dashboard.deleteTargetConfirm", { title: job.title })))
      return;
    setDeletingJobId(job.id);
    setError("");
    try {
      await deleteJob(job.id);
      if (initialJob?.id === job.id) onJobLoaded?.(undefined);
      await load();
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : t("dashboard.deleteTargetFailed"),
      );
    } finally {
      setDeletingJobId(null);
    }
  };

  if (loading)
    return (
      <main className="command-dashboard">
        <section className="dashboard-loading-shell" aria-live="polite">
          <span className="dashboard-loader" aria-hidden="true" />
          <p>{t("dashboard.loading")}</p>
        </section>
      </main>
    );
  if (error)
    return (
      <main className="command-dashboard">
        <PageFeedback
          kind="error"
          message={error}
          actionLabel={t("dashboard.refreshStatus")}
          onAction={() => void load()}
        />
      </main>
    );
  if (!summary) return null;

  const metrics = [
    {
      value: summary.confirmed_experiences,
      label: t("dashboard.confirmedExperiences"),
      detail: t("dashboard.pendingExperiences", {
        n: summary.pending_experiences,
      }),
      accent: "blue",
      detailTone: summary.pending_experiences > 0 ? "attention" : "clear",
      target: "profile" as PageId,
    },
    {
      value: summary.job_total,
      label: t("dashboard.analyzedJobs"),
      detail: summary.latest_job
        ? `${summary.latest_job.company} · ${summary.latest_job.title}`
        : t("dashboard.noTarget"),
      accent: "violet",
      target: "tracker" as PageId,
    },
    {
      // Show all saved material versions. Counting only distinct types (or
      // only the latest role) misleadingly produces 0/1/2 even when the user
      // already has a substantial material history.
      value: summary.material_count,
      label: t("dashboard.generatedMaterialTypes"),
      detail: summary.latest_material_type
        ? t("dashboard.materialVersionDetail", {
            type: summary.latest_material_type,
            n: summary.material_count,
          })
        : t("dashboard.notGenerated"),
      accent: "amber",
      target: "builder" as PageId,
    },
    {
      value: summary.active_applications,
      label: t("dashboard.activeApps"),
      detail: t("dashboard.trackedTotal", { n: summary.tracker_total }),
      accent: "mint",
      target: "tracker" as PageId,
    },
  ];

  return (
    <main className="command-dashboard">
      <header className="command-hero">
        <div className="command-hero-copy">
          <p className="eyebrow">
            <strong>APPLYEASE</strong>
            <span>
              {t("dashboard.commandCenter").replace(
                /^APPLYEASE\s*[·.]\s*/i,
                "",
              )}
            </span>
          </p>
          <h1 className="command-hero-title">{t("dashboard.hero.title")}</h1>
          <p>{t("dashboard.hero.sub")}</p>
        </div>
        <div className="command-hero-action">
          <button
            type="button"
            onClick={() => onNavigate("profile")}
          >
            {t("dashboard.startNow")}
          </button>
        </div>
      </header>

      {((summary.urgent_deadlines_count || 0) > 0 || summary.upcoming_deadlines.length > 0) && (
        <section className="dashboard-urgent-banner dashboard-date-summary" role="status">
          <div className="date-summary-column date-summary-urgent">
            <span className="dashboard-urgent-mark" aria-hidden="true">!</span>
            <div>
              <strong>{t("dashboard.urgentDeadlineTitle", { n: summary.urgent_deadlines_count || 0 })}</strong>
              <p>{t("dashboard.urgentDeadlineHelp")}</p>
            </div>
            <button type="button" onClick={() => navigate("tracker")}>
              {t("dashboard.manageDates")} →
            </button>
          </div>
          <div className="date-summary-column date-summary-upcoming">
            <div className="date-summary-heading">
              <span aria-hidden="true">◷</span>
              <strong>{t("dashboard.attentionDates")}</strong>
            </div>
            <div className="date-summary-list">
              {summary.upcoming_deadlines.slice(0, 3).map((item) => {
                const kindLabel = item.kind === "interview"
                  ? t("dashboard.interview")
                  : item.kind === "follow_up" ? t("dashboard.followUp") : t("dashboard.deadline");
                return (
                  <button
                    type="button"
                    className={`date-summary-event${item.is_overdue ? " overdue" : ""}`}
                    key={`${item.id}-${item.kind}-${item.deadline}`}
                    onClick={() => onNavigate("tracker", item.job_id ? { id: item.job_id, title: item.role, company: item.company } : undefined)}
                  >
                    <time dateTime={item.deadline}>{item.deadline}</time>
                    <span>{kindLabel} · {item.company} · {item.role}</span>
                    {item.is_overdue && <em>{t("dashboard.overdue")}</em>}
                  </button>
                );
              })}
            </div>
          </div>
        </section>
      )}

      <section
        className="dashboard-metrics"
        aria-label={t("dashboard.overviewLabel")}
      >
        {metrics.map((metric, index) => (
          <article
            className={`dashboard-metric metric-${metric.accent}`}
            key={metric.label}
          >
            <span className="metric-icon" aria-hidden="true">
              {metricMarks[index]}
            </span>
            <div>
              <strong>{metric.value}</strong>
              <span>{metric.label}</span>
              <button
                type="button"
                className={
                  metric.detailTone
                    ? `metric-detail metric-detail-${metric.detailTone} metric-detail-action`
                    : "metric-detail metric-detail-action"
                }
                onClick={() => navigate(metric.target)}
                aria-label={t("dashboard.openMetric", { label: metric.label })}
              >
                {metric.detail}
                <span aria-hidden="true">→</span>
              </button>
            </div>
          </article>
        ))}
      </section>

      <section
        className="role-command-center"
        aria-label={t("dashboard.roleCenter")}
      >
        <div className="panel-heading">
          <div>
            <h2>{t("dashboard.roleCenter")}</h2>
          </div>
        </div>
        {(summary.job_workspaces || []).length ? (
          <div className="role-command-grid">
            {(summary.job_workspaces || []).map((job) => (
              <article className="role-command-card" key={job.id}>
                <p>{job.company || t("dashboard.noTarget")}</p>
                <h3>{job.title}</h3>
                <div className="tags">
                  <span>
                    {t("dashboard.roleMatch", {
                      level: t(`job.matchLevel.${matchLevelTranslationKey(resolveMatchLevel(job.match_level, job.match_score))}`),
                    })}
                  </span>
                  <span>
                    {t("dashboard.roleEvidence", { n: job.evidence_count })}
                  </span>
                  <span>
                    {t("dashboard.roleMaterials", { n: job.material_count })}
                  </span>
                </div>
                {job.missing_skills.length > 0 && (
                  <section
                    className="role-priority-gaps"
                    aria-label={t("dashboard.roleGapsTitle")}
                  >
                    <strong>{t("dashboard.roleGapsTitle")}</strong>
                    <ul>
                      {job.missing_skills.map((skill) => (
                        <li key={skill}>{skill}</li>
                      ))}
                    </ul>
                  </section>
                )}
                <button
                  type="button"
                  className="role-workspace-action"
                  onClick={() => onNavigate("tracker", job)}
                >
                  {t("dashboard.roleContinue")} →
                </button>
                <button
                  type="button"
                  className="role-workspace-delete"
                  disabled={deletingJobId !== null}
                  onClick={() => void removeJobWorkspace(job)}
                >
                  {deletingJobId === job.id
                    ? t("shared.saving")
                    : t("dashboard.deleteTarget", { title: job.title })}
                </button>
              </article>
            ))}
          </div>
        ) : (
          <p className="privacy-note">{t("dashboard.roleCenterEmpty")}</p>
        )}
      </section>

    </main>
  );
}
