import { screen } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  previewJobAnalysis: vi.fn(),
  saveAnalyzedJob: vi.fn(),
  getMatchReport: vi.fn(),
  importJobUrl: vi.fn(),
  importJobScreenshot: vi.fn(),
}));
vi.mock("../../services/jobApi", () => api);
import { JobAnalysisPage } from "./JobAnalysisPage";

const job = {
  id: 3,
  title: "AI Intern",
  company: "Example",
  description: "Python and Docker are required for this internship.",
  required_skills: ["Python", "Docker"],
  preferred_skills: [],
  responsibilities: [],
  qualifications: [],
  created_at: "2026-08-13",
};
const report = {
  job,
  overall_score: 50,
  matched_skills: ["Python"],
  missing_skills: ["Docker"],
  evidence: [
    {
      requirement: "Python",
      experience_id: 7,
      experience_title: "ML Project",
      evidence: "Built a forecasting model with Python.",
    },
  ],
  considered_experience_ids: [7],
};

describe("JobAnalysisPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.previewJobAnalysis.mockResolvedValue({ ...report, job: { ...job, id: 0 } });
    api.saveAnalyzedJob.mockResolvedValue(job);
    api.getMatchReport.mockResolvedValue(report);
    api.importJobUrl.mockResolvedValue({
      title: "Quant Intern",
      company: "Jane Street",
      description: job.description,
      location: "Hong Kong",
      deadline: "30 September",
      source_url: "https://jobs.example.com/quant",
    });
  });

  it("imports a reviewable public-job draft before analysis", async () => {
    const user = userEvent.setup();
    renderWithProviders(<JobAnalysisPage />);

    await user.type(
      screen.getByLabelText("公开 HTTPS 职位链接"),
      "https://jobs.example.com/quant",
    );

    await user.click(screen.getByRole("button", { name: "从链接导入" }));

    expect(api.importJobUrl).toHaveBeenCalledWith(
      "https://jobs.example.com/quant",
    );

    expect(await screen.findByDisplayValue("Quant Intern")).toBeInTheDocument();

    expect(screen.getByDisplayValue(job.description)).toBeInTheDocument();

    expect(screen.queryByText(/地点：Hong Kong/)).not.toBeInTheDocument();
  });

  it("shows loading copy only on the action that is actually running", async () => {
    let resolveImport: ((value: {
      title: string;
      company: string;
      description: string;
      location: string;
      deadline: string;
      source_url: string;
    }) => void) | undefined;
    api.importJobUrl.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveImport = resolve;
        }),
    );
    const user = userEvent.setup();
    renderWithProviders(<JobAnalysisPage />);

    await user.type(
      screen.getByLabelText("公开 HTTPS 职位链接"),
      "https://jobs.example.com/quant",
    );
    await user.click(screen.getByRole("button", { name: "从链接导入" }));

    expect(screen.getByRole("button", { name: "导入中..." })).toBeDisabled();
    expect(screen.getByRole("button", { name: "从截图导入" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "分析职位" })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "识别中..." })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "分析中..." })).not.toBeInTheDocument();

    resolveImport?.({
      title: "Quant Intern",
      company: "Jane Street",
      description: job.description,
      location: "Hong Kong",
      deadline: "30 September",
      source_url: "https://jobs.example.com/quant",
    });
    expect(await screen.findByDisplayValue("Quant Intern")).toBeInTheDocument();
  });

  it("analyzes a posting and renders score, gaps, and grounded evidence", async () => {
    const user = userEvent.setup();
    const onOpenResourcePlan = vi.fn();
    renderWithProviders(
      <JobAnalysisPage onOpenResourcePlan={onOpenResourcePlan} />,
    );

    await user.type(screen.getByLabelText("职位名称"), "AI Intern");

    await user.type(screen.getByLabelText("公司"), "Example");

    await user.type(screen.getByLabelText("职位描述"), job.description);

    await user.click(screen.getByRole("button", { name: "分析职位" }));

    expect(api.previewJobAnalysis).toHaveBeenCalledWith({
      title: "AI Intern",
      company: "Example",
      description: job.description,
    });

    expect(await screen.findByText("50")).toBeInTheDocument();

    expect(
      screen
        .getAllByText("Docker")
        .find((element) => element.classList.contains("missing")),
    ).toBeTruthy();

    expect(
      screen.getByText("Built a forecasting model with Python."),
    ).toBeInTheDocument();
    expect(screen.getByText("要将这个职位加入职位工作台吗？")).toBeInTheDocument();
    expect(screen.getByText("申请证据地图")).toBeInTheDocument();
    expect(screen.getByText("由 ML Project 支持")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "为这些缺口生成补强计划" }),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "加入职位工作台" }));
    expect(api.saveAnalyzedJob).toHaveBeenCalledWith({
      title: "AI Intern",
      company: "Example",
      description: job.description,
      required_skills: ["Python", "Docker"],
      preferred_skills: [],
      responsibilities: [],
      qualifications: [],
    });
    expect(
      await screen.findByRole("button", { name: "为这些缺口生成补强计划" }),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "为这些缺口生成补强计划" }),
    );
    expect(onOpenResourcePlan).toHaveBeenCalledWith({
      id: 3,
      title: "AI Intern",
      company: "Example",
    });
  });

  it("disables submission for a short description", async () => {
    const user = userEvent.setup();
    renderWithProviders(<JobAnalysisPage />);

    await user.type(screen.getByLabelText("职位描述"), "too short");

    expect(screen.getByRole("button", { name: "分析职位" })).toBeDisabled();
  });

  it("shows API failures and clears the busy state", async () => {
    const user = userEvent.setup();
    api.previewJobAnalysis.mockRejectedValue(new Error("AI 服务超时"));
    renderWithProviders(<JobAnalysisPage />);

    await user.type(screen.getByLabelText("职位描述"), job.description);

    await user.click(screen.getByRole("button", { name: "分析职位" }));

    expect(await screen.findByText("AI 服务超时")).toHaveClass("error");

    expect(screen.getByRole("button", { name: "分析职位" })).toBeEnabled();
  });
});
