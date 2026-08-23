import { screen, waitFor } from "@testing-library/react";
import { renderWithProviders } from "../../test/render";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getDashboardSummary: vi.fn() }));
vi.mock("../../services/dashboardApi", () => api);
const jobsApi = vi.hoisted(() => ({ deleteJob: vi.fn() }));
vi.mock("../../services/jobApi", () => jobsApi);

import { DashboardPage } from "./DashboardPage";
import type { DashboardSummary } from "../../types/dashboard";

const summary: DashboardSummary = {
  experience_total: 2,
  confirmed_experiences: 1,
  pending_experiences: 1,
  job_total: 1,
  latest_job: { id: 4, title: "AI Intern", company: "Polymer" },
  material_count: 0,
  material_types: [],
  latest_material_type: null,
  application_id: null,
  questions_total: 0,
  answers_ready: 0,
  tracker_total: 0,
  active_applications: 0,
  upcoming_deadlines: [],
  steps: [
    {
      key: "profile",
      label: "经历库",
      description: "上传、核对并确认事实",
      status: "complete",
      target: "profile",
    },
    {
      key: "jobs",
      label: "职位分析",
      description: "提取要求与匹配证据",
      status: "complete",
      target: "jobs",
    },
    {
      key: "builder",
      label: "申请材料",
      description: "生成 Resume 与 Cover Letter",
      status: "current",
      target: "builder",
    },
    {
      key: "form",
      label: "申请问题",
      description: "识别并审核表单答案",
      status: "pending",
      target: "form",
    },
    {
      key: "tracker",
      label: "申请追踪",
      description: "保存状态与下一步日期",
      status: "pending",
      target: "tracker",
    },
  ],
  next_action: {
    title: "生成申请材料",
    description: "为最新职位生成 Resume 和 Cover Letter。",
    target: "builder",
  },
  job_workspaces: [
    {
      id: 4,
      title: "AI Intern",
      company: "Polymer",
      match_score: 76,
      evidence_count: 1,
      missing_skills: ["SQL"],
      material_count: 0,
      answers_ready: 0,
      questions_total: 0,
      next_target: "builder",
      progress: 40,
      steps: [
        {
          key: "profile",
          label: "经历库",
          description: "",
          status: "complete",
          target: "profile",
        },
        {
          key: "jobs",
          label: "职位分析",
          description: "",
          status: "complete",
          target: "jobs",
        },
        {
          key: "builder",
          label: "申请材料",
          description: "",
          status: "current",
          target: "builder",
        },
        {
          key: "form",
          label: "申请问题",
          description: "",
          status: "pending",
          target: "form",
        },
        {
          key: "tracker",
          label: "申请追踪",
          description: "",
          status: "pending",
          target: "tracker",
        },
      ],
    },
  ],
};

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getDashboardSummary.mockResolvedValue(summary);
    jobsApi.deleteJob.mockResolvedValue(undefined);
  });

  it("shows the instrument metrics and current job", async () => {
    renderWithProviders(<DashboardPage onNavigate={vi.fn()} />);

    expect(await screen.findByText("职位工作台")).toBeInTheDocument();

    expect(screen.getAllByText("已确认经历").length).toBeGreaterThan(0);

    expect(
      screen.getByRole("button", { name: "打开已生成材料" }),
    ).toBeInTheDocument();
    // A global 2/5 or 100% progress score is misleading when a user has
    // multiple target roles. Completion belongs to each role workspace.
    expect(screen.queryByText("已完成 2/5 个阶段")).not.toBeInTheDocument();
    expect(screen.queryByText("已完成 2/5 步 · 40%")).not.toBeInTheDocument();
    expect(screen.getByText("优先缺口")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
  });

  it("opens the Experience Bank when the dashboard start action is clicked", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();

    renderWithProviders(<DashboardPage onNavigate={onNavigate} />);

    await user.click(
      (await screen.findAllByRole("button", { name: /现在开始/ }))[0],
    );

    expect(onNavigate).toHaveBeenCalledWith("profile");
  });

  it("opens the selected role's tracker workspace from its instrument card", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderWithProviders(<DashboardPage onNavigate={onNavigate} />);

    await user.click(await screen.findByRole("button", { name: /职位工作台/ }));

    expect(onNavigate).toHaveBeenCalledWith(
      "tracker",
      expect.objectContaining({
        id: 4,
        title: "AI Intern",
        company: "Polymer",
      }),
    );
  });

  it("deletes a role workspace and refreshes the dashboard", async () => {
    const user = userEvent.setup();
    vi.spyOn(window, "confirm").mockReturnValue(true);
    renderWithProviders(<DashboardPage onNavigate={vi.fn()} />);

    await user.click(await screen.findByRole("button", { name: "删除 AI Intern" }));

    await waitFor(() => expect(jobsApi.deleteJob).toHaveBeenCalledWith(4));
    expect(api.getDashboardSummary).toHaveBeenCalledTimes(2);
  });

  it("keeps an explicitly selected role active even when the dashboard snapshot has another latest role", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    const selectedJob = {
      id: 19,
      title: "AI and Quantitative Technology Intern",
      company: "Polymer Capital",
    };
    const onJobLoaded = vi.fn();
    renderWithProviders(
      <DashboardPage
        onNavigate={onNavigate}
        initialJob={selectedJob}
        onJobLoaded={onJobLoaded}
      />,
    );
    await user.click(
      (await screen.findAllByRole("button", { name: /现在开始/ }))[0],
    );
    expect(onNavigate).toHaveBeenCalledWith("profile");
    expect(onJobLoaded).not.toHaveBeenCalled();
  });

  it("makes each summary detail an actionable route", async () => {
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderWithProviders(<DashboardPage onNavigate={onNavigate} />);

    await user.click(await screen.findByRole("button", { name: "打开已分析职位" }));
    expect(onNavigate).toHaveBeenCalledWith("tracker", summary.latest_job);
  });

  it("allows retry after a dashboard request fails", async () => {
    api.getDashboardSummary
      .mockRejectedValueOnce(new Error("服务暂时不可用"))
      .mockResolvedValueOnce(summary);

    const user = userEvent.setup();
    renderWithProviders(<DashboardPage onNavigate={vi.fn()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "服务暂时不可用",
    );

    await user.click(screen.getByRole("button", { name: "重新加载" }));

    await waitFor(() =>
      expect(screen.getByText("职位工作台")).toBeInTheDocument(),
    );
  });

  it("distinguishes follow-up and overdue events", async () => {
    api.getDashboardSummary.mockResolvedValueOnce({
      ...summary,
      upcoming_deadlines: [
        {
          id: 8,
          company: "FollowCo",
          role: "Research Intern",
          deadline: "2026-08-14",
          status: "applied",
          kind: "follow_up",
        },
        {
          id: 9,
          company: "LateCo",
          role: "AI Intern",
          deadline: "2026-08-10",
          status: "applied",
          kind: "deadline",
          is_overdue: true,
        },
      ],
    });

    renderWithProviders(<DashboardPage onNavigate={vi.fn()} />);

    expect(await screen.findByText(/待跟进/)).toBeInTheDocument();

    expect(screen.getByText("已逾期")).toBeInTheDocument();
  });

  it("shows a saved deadline even when it is more than 14 days away", async () => {
    api.getDashboardSummary.mockResolvedValueOnce({
      ...summary,
      upcoming_deadlines: [
        {
          id: 12,
          job_id: 4,
          company: "Polymer",
          role: "AI Intern",
          deadline: "2026-10-20",
          status: "saved",
          kind: "deadline",
        },
      ],
    });
    const user = userEvent.setup();
    const onNavigate = vi.fn();
    renderWithProviders(<DashboardPage onNavigate={onNavigate} />);

    expect(await screen.findByText("2026-10-20")).toBeInTheDocument();
    await user.click(screen.getByText("2026-10-20"));
    expect(onNavigate).toHaveBeenCalledWith(
      "tracker",
      expect.objectContaining({ id: 4, company: "Polymer" }),
    );
  });
});
