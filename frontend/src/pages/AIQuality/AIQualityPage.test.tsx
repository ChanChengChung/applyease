import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getAIMetrics: vi.fn() }));
vi.mock("../../services/aiObservationApi", () => api);
import { AIQualityPage } from "./AIQualityPage";

const metrics = {
  period_days: 30,
  generated_at: "2026-08-13T00:00:00Z",
  total_feature_calls: 4,
  ai_successes: 3,
  rule_fallbacks: 1,
  errors: 0,
  success_rate: 0.75,
  fallback_rate: 0.25,
  provider_attempts: 5,
  prompt_versions: ["job-requirements-v1"],
  by_provider: [
    {
      provider: "ollama",
      attempts: 5,
      successes: 3,
      errors: 2,
      success_rate: 0.6,
      average_latency_ms: 1200,
      p95_latency_ms: 2000,
    },
  ],
  by_feature: [
    {
      feature: "job_requirements",
      total: 4,
      ai_successes: 3,
      rule_fallbacks: 1,
      errors: 0,
      success_rate: 0.75,
    },
  ],
  recent_events: [],
  privacy_notice: "Only content-free operational metadata is stored.",
};

describe("AIQualityPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getAIMetrics.mockResolvedValue(metrics);
  });

  it("shows success, fallback and latency metrics", async () => {
    renderWithProviders(<AIQualityPage />);

    expect(await screen.findByText("75%")).toBeInTheDocument();

    expect(screen.getByText("25%")).toBeInTheDocument();

    expect(screen.getByText("1200 ms")).toBeInTheDocument();

    expect(screen.getByText("职位要求分析")).toBeInTheDocument();

    expect(screen.getByText(/不保存 CV/)).toBeInTheDocument();
  });

  it("reloads metrics when the period changes", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AIQualityPage />);

    await screen.findByText("75%");

    await user.selectOptions(screen.getByLabelText("时间范围"), "7");

    expect(api.getAIMetrics).toHaveBeenLastCalledWith(7);
  });

  it("shows an explicit empty state", async () => {
    api.getAIMetrics.mockResolvedValue({
      ...metrics,
      total_feature_calls: 0,
      ai_successes: 0,
      rule_fallbacks: 0,
      success_rate: 0,
      fallback_rate: 0,
      provider_attempts: 0,
      by_provider: [],
      by_feature: [],
    });

    renderWithProviders(<AIQualityPage />);

    expect(await screen.findByText("还没有 AI 调用数据")).toBeInTheDocument();
  });
});
