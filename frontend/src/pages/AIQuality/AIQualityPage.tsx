import { useEffect, useState } from "react";
import { PageFeedback } from "../../components/PageFeedback";
import { getAIMetrics } from "../../services/aiObservationApi";
import type { AIMetrics } from "../../types/aiObservation";
import { useT } from "../../i18n/LanguageProvider";

const percent = (value: number) => `${Math.round(value * 100)}%`;

export function AIQualityPage() {
  const [days, setDays] = useState(30);

  const [metrics, setMetrics] = useState<AIMetrics | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  const t = useT();

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setMetrics(await getAIMetrics(days));
    } catch (e) {
      setError(e instanceof Error ? e.message : t("ai.loading"));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [days]);

  const featureName = (key: string) => {
    const map: Record<string, string> = {
      experience_extraction: t("ai.feature.experience_extraction"),
      job_requirements: t("ai.feature.job_requirements"),
      job_match: t("ai.feature.job_match"),
      resume: t("ai.feature.resume"),
      cover_letter: t("ai.feature.cover_letter"),
      application_answer: t("ai.feature.application_answer"),
      form_analysis: t("ai.feature.form_analysis"),
      screenshot_ocr: t("ai.feature.screenshot_ocr"),
    };

    return map[key] || key;
  };

  return (
    <main className="product-page quality-page">
      <header className="product-hero">
        <div>
          <p className="eyebrow">AI QUALITY · PRIVATE BY DESIGN</p>
          <h1>{t("ai.hero.title")}</h1>
          <p className="sub">{t("ai.hero.sub")}</p>
        </div>
        <div className="hero-orb hero-orb-quality" aria-hidden="true">
          <span>◌</span>
        </div>
      </header>
      <section className="product-content">
        <div className="section-heading">
          <div>
            <p className="section-kicker">SYSTEM OBSERVABILITY</p>
            <h2>{t("ai.recent")}</h2>
          </div>
          <label>
            {t("ai.range")}
            <select
              aria-label={t("ai.range")}
              value={days}
              onChange={(event) => setDays(Number(event.target.value))}
            >
              <option value={7}>7 {t("ai.range")}</option>
              <option value={30}>30 {t("ai.range")}</option>
              <option value={90}>90 {t("ai.range")}</option>
            </select>
          </label>
        </div>

        {loading ? (
          <section className="card dashboard-state" aria-live="polite">
            {t("ai.loading")}
          </section>
        ) : error ? (
          <PageFeedback
            kind="error"
            message={error}
            actionLabel={t("ai.reload")}
            onAction={() => void load()}
          />
        ) : (
          metrics && (
            <>
              <section
                className="metric-grid"
                aria-label={t("ai.metricsLabel")}
              >
                <article className="metric">
                  <strong>{metrics.total_feature_calls}</strong>
                  <span>{t("ai.calls")}</span>
                  <small>
                    {t("ai.providerAttempts", { n: metrics.provider_attempts })}
                  </small>
                </article>
                <article className="metric">
                  <strong>{percent(metrics.success_rate)}</strong>
                  <span>{t("ai.successRate")}</span>
                  <small>
                    {t("ai.aiSuccesses", { n: metrics.ai_successes })}
                  </small>
                </article>
                <article className="metric">
                  <strong>{percent(metrics.fallback_rate)}</strong>
                  <span>{t("ai.fallbackRate")}</span>
                  <small>
                    {t("ai.ruleFallbacks", { n: metrics.rule_fallbacks })}
                  </small>
                </article>
                <article className="metric">
                  <strong>{metrics.errors}</strong>
                  <span>{t("ai.errors")}</span>
                  <small>{t("ai.errorsNote")}</small>
                </article>
              </section>

              {!metrics.total_feature_calls ? (
                <section className="empty">
                  <h2>{t("ai.noData")}</h2>
                  <p>{t("ai.noDataHint")}</p>
                </section>
              ) : (
                <>
                  <section className="card">
                    <h2>{t("ai.providerTable")}</h2>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>{t("ai.col.provider")}</th>
                            <th>{t("ai.col.attempts")}</th>
                            <th>{t("ai.col.success")}</th>
                            <th>{t("ai.col.avgLatency")}</th>
                            <th>{t("ai.col.p95Latency")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {metrics.by_provider.map((item) => (
                            <tr key={item.provider}>
                              <td>{item.provider}</td>
                              <td>{item.attempts}</td>
                              <td>{percent(item.success_rate)}</td>
                              <td>{item.average_latency_ms} ms</td>
                              <td>{item.p95_latency_ms} ms</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                  <section className="card">
                    <h2>{t("ai.featureTable")}</h2>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>{t("ai.col.feature")}</th>
                            <th>{t("ai.col.calls")}</th>
                            <th>{t("ai.col.aiSuccess")}</th>
                            <th>{t("ai.col.fallback")}</th>
                            <th>{t("ai.col.error")}</th>
                          </tr>
                        </thead>
                        <tbody>
                          {metrics.by_feature.map((item) => (
                            <tr key={item.feature}>
                              <td>{featureName(item.feature)}</td>
                              <td>{item.total}</td>
                              <td>{item.ai_successes}</td>
                              <td>{item.rule_fallbacks}</td>
                              <td>{item.errors}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}
              <p className="privacy-note">{t("ai.privacyNotice")}</p>
            </>
          )
        )}
      </section>
    </main>
  );
}
