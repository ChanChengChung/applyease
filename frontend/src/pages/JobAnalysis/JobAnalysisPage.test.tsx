import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  previewJobAnalysis: vi.fn(),
  previewManualJobAnalysis: vi.fn(),
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
    window.sessionStorage.clear();
    api.previewJobAnalysis.mockResolvedValue({ ...report, job: { ...job, id: 0 } });
    api.previewManualJobAnalysis.mockResolvedValue({ ...report, job: { ...job, id: 0 } });
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

    expect(await screen.findByRole("heading", { name: "Quant Intern" })).toBeInTheDocument();
    expect(screen.getByText(/地点：Hong Kong/)).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "手动建立职位简介" })).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /查看完整分析结果/ })).toHaveAttribute(
      "href",
      "#job-analysis-result",
    );
  });

  it("asks the student to manually confirm sensitive eligibility requirements", async () => {
    const user = userEvent.setup();
    api.previewManualJobAnalysis.mockResolvedValue({
      ...report,
      job: { ...job, id: 0 },
      eligibility_checks: [
        {
          kind: "work_authorization",
          requirement: "Must have right to work in Hong Kong.",
          status: "needs_confirmation",
          evidence: "",
        },
      ],
    });
    renderWithProviders(<JobAnalysisPage />);

    await user.type(screen.getByLabelText("其他已知要求"), job.description);
    await user.click(screen.getByRole("button", { name: "分析这份职位简介" }));

    expect(await screen.findByText("申请前请先确认资格")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "我符合这项要求" }));
    expect(await screen.findByText("可以申请，但需先补强")).toBeInTheDocument();
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
    expect(screen.getByRole("button", { name: "分析这份职位简介" })).toBeDisabled();
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
    expect(await screen.findByRole("heading", { name: "Quant Intern" })).toBeInTheDocument();
    await waitFor(() =>
      expect(api.previewJobAnalysis).toHaveBeenCalledWith({
        title: "Quant Intern",
        company: "Jane Street",
        description: job.description,
      }),
    );
  });

  it("analyzes a posting and renders score, gaps, and grounded evidence", async () => {
    const user = userEvent.setup();
    const onOpenResourcePlan = vi.fn();
    renderWithProviders(
      <JobAnalysisPage onOpenResourcePlan={onOpenResourcePlan} />,
    );

    await user.type(screen.getByLabelText("职位名称"), "AI Intern");

    await user.type(screen.getByLabelText("公司"), "Example");

    await user.type(screen.getByLabelText("其他已知要求"), job.description);

    await user.click(screen.getByRole("button", { name: "分析这份职位简介" }));

    expect(api.previewManualJobAnalysis).toHaveBeenCalledWith({
      title: "AI Intern",
      company: "Example",
      job_category: "",
      location: "",
      required_skills: [],
      responsibilities: [],
      additional_details: job.description,
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

  it("requires at least one manual role fact before analysis", async () => {
    const user = userEvent.setup();
    renderWithProviders(<JobAnalysisPage />);

    expect(screen.getByRole("button", { name: "分析这份职位简介" })).toBeDisabled();
    await user.type(screen.getByLabelText("技能要求"), "Python");

    expect(screen.getByRole("button", { name: "分析这份职位简介" })).toBeEnabled();
  });

  it("restores an unsaved analysis after the workspace is remounted", async () => {
    const user = userEvent.setup();
    const firstRender = renderWithProviders(<JobAnalysisPage />);

    await user.type(screen.getByLabelText("职位名称"), "AI Intern");
    await user.type(screen.getByLabelText("公司"), "Example");
    await user.type(screen.getByLabelText("其他已知要求"), job.description);
    await user.click(screen.getByRole("button", { name: "分析这份职位简介" }));
    expect(await screen.findByText("50")).toBeInTheDocument();
    await waitFor(() =>
      expect(window.sessionStorage.getItem("applyease.job-analysis-draft.v1")).toContain("AI Intern"),
    );

    firstRender.unmount();
    renderWithProviders(<JobAnalysisPage />);

    expect(await screen.findByText("50")).toBeInTheDocument();
    expect(screen.getByDisplayValue("AI Intern")).toBeInTheDocument();
  });

  it("shows API failures and clears the busy state", async () => {
    const user = userEvent.setup();
    api.previewManualJobAnalysis.mockRejectedValue(new Error("AI 服务超时"));
    renderWithProviders(<JobAnalysisPage />);

    await user.type(screen.getByLabelText("其他已知要求"), job.description);

    await user.click(screen.getByRole("button", { name: "分析这份职位简介" }));

    expect(await screen.findByText("AI 服务超时")).toHaveClass("error");

    expect(screen.getByRole("button", { name: "分析这份职位简介" })).toBeEnabled();
  });
});
