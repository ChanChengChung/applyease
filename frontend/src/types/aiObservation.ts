export type AIProviderMetric = {
  provider: string;
  attempts: number;
  successes: number;
  errors: number;
  success_rate: number;
  average_latency_ms: number;
  p95_latency_ms: number;
};
export type AIFeatureMetric = {
  feature: string;
  total: number;
  ai_successes: number;
  rule_fallbacks: number;
  errors: number;
  success_rate: number;
};
export type AIRecentEvent = {
  feature: string;
  provider: string;
  model: string;
  prompt_version: string;
  status: string;
  latency_ms: number;
  error_category: string | null;
  created_at: string;
};
export type AIMetrics = {
  period_days: number;
  generated_at: string;
  total_feature_calls: number;
  ai_successes: number;

  rule_fallbacks: number;
  errors: number;
  success_rate: number;
  fallback_rate: number;

  provider_attempts: number;
  prompt_versions: string[];
  by_provider: AIProviderMetric[];

  by_feature: AIFeatureMetric[];
  recent_events: AIRecentEvent[];
  privacy_notice: string;
};
